"""
Assets Router
─────────────
Handles asset registration, fingerprinting, and retrieval.

POST   /assets/upload          → Upload and register a new asset
GET    /assets/                → List all assets
GET    /assets/{id}            → Get asset details
DELETE /assets/{id}            → Soft-delete asset
POST   /assets/{id}/verify-watermark → Verify watermark on submitted file
"""

import mimetypes
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from loguru import logger
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Asset, AssetType, FrameHash, Organization
from routers.auth import get_default_org
from schemas import AssetOut, AssetListOut
from services.faiss_index import faiss_manager
from services.fingerprint import (
    compute_image_hashes,
    compute_video_fingerprints,
    hash_to_vector,
)
from services.storage import save_file
from services.watermark import verify_asset_ownership

router = APIRouter(prefix="/assets", tags=["Assets"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/mpeg", "video/quicktime", "video/x-msvideo", "video/webm"}
MAX_FILE_SIZE_MB = 500


def _detect_asset_type(mime_type: str) -> AssetType:
    if mime_type in ALLOWED_IMAGE_TYPES:
        return AssetType.IMAGE
    elif mime_type in ALLOWED_VIDEO_TYPES:
        return AssetType.VIDEO
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail=f"Unsupported file type: {mime_type}. Allowed: images and videos.",
    )


@router.post("/upload", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    rights_owner: Optional[str] = Form(None),
    rights_description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # comma-separated
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(get_default_org),
):
    """
    Upload and register a media asset.

    - Computes perceptual fingerprints (pHash, dHash, aHash, wHash)
    - Adds fingerprint to FAISS index for fast future matching
    - Stores asset metadata in PostgreSQL
    """
    # ── Validate file ────────────────────────────────────────────────────────
    file_bytes = await file.read()
    file_size = len(file_bytes)

    if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {MAX_FILE_SIZE_MB}MB",
        )

    mime_type = (
        file.content_type
        or mimetypes.guess_type(file.filename or "")[0]
        or "application/octet-stream"
    )
    asset_type = _detect_asset_type(mime_type)
    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    logger.info(f"Processing upload: {file.filename} ({file_size / 1024:.1f}KB, {mime_type})")

    # ── Compute fingerprints ─────────────────────────────────────────────────
    phash = dhash = ahash = whash = None
    duration = frame_count = None
    frame_hashes_data = []

    if asset_type == AssetType.IMAGE:
        hashes = compute_image_hashes(file_bytes)
        phash = hashes["phash"]
        dhash = hashes["dhash"]
        ahash = hashes["ahash"]
        whash = hashes["whash"]

    elif asset_type == AssetType.VIDEO:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            video_data = compute_video_fingerprints(tmp_path)
            duration = video_data["duration_seconds"]
            frame_count = len(video_data["keyframes"])
            frame_hashes_data = video_data["keyframes"]
            if frame_hashes_data:
                phash = frame_hashes_data[0]["phash"]
                dhash = frame_hashes_data[0]["dhash"]
        finally:
            os.unlink(tmp_path)

    # ── Store file ───────────────────────────────────────────────────────────
    file_path = await save_file(file_bytes, file.filename or "upload", org.id)

    # ── Create Asset record ──────────────────────────────────────────────────
    asset = Asset(
        org_id=org.id,
        title=title,
        description=description,
        asset_type=asset_type,
        original_filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        mime_type=mime_type,
        phash=phash,
        dhash=dhash,
        ahash=ahash,
        whash=whash,
        duration_seconds=duration,
        frame_count=frame_count,
        rights_owner=rights_owner or org.name,
        rights_description=rights_description,
        is_watermarked=False,
        watermark_id=None,
        is_registered=True,
        tags=tag_list,
    )
    db.add(asset)
    await db.flush()  # get asset.id before FAISS indexing

    # ── Add to FAISS index ───────────────────────────────────────────────────
    if phash:
        vec = hash_to_vector(phash)
        faiss_id = faiss_manager.add(vec, asset_id=asset.id)
        asset.faiss_index_id = faiss_id
        logger.info(f"Added to FAISS index at position {faiss_id}")

    # ── Store video frame hashes ─────────────────────────────────────────────
    for kf in frame_hashes_data:
        frame_vec = hash_to_vector(kf["phash"])
        frame_faiss_id = faiss_manager.add(frame_vec, asset_id=asset.id, frame_id=None)
        fh = FrameHash(
            asset_id=asset.id,
            frame_number=kf["frame_number"],
            timestamp_seconds=kf["timestamp_seconds"],
            phash=kf["phash"],
            faiss_index_id=frame_faiss_id,
        )
        db.add(fh)

    await db.commit()
    await db.refresh(asset)

    logger.info(f"Asset registered: {asset.id} — {asset.title}")
    return asset


@router.get("/", response_model=AssetListOut)
async def list_assets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    asset_type: Optional[AssetType] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(get_default_org),
):
    """List all assets."""
    query = select(Asset).where(
        and_(Asset.org_id == org.id, Asset.is_active == True)
    )

    if asset_type:
        query = query.where(Asset.asset_type == asset_type)
    if search:
        query = query.where(Asset.title.ilike(f"%{search}%"))

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Asset.registered_at.desc())
    results = (await db.execute(query)).scalars().all()

    return AssetListOut(items=list(results), total=total, page=page, page_size=page_size)


@router.get("/{asset_id}", response_model=AssetOut)
async def get_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(get_default_org),
):
    """Get a single asset by ID."""
    asset = await db.get(Asset, asset_id)
    if not asset or asset.org_id != org.id or not asset.is_active:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(get_default_org),
):
    """Soft-delete an asset and remove from FAISS index."""
    asset = await db.get(Asset, asset_id)
    if not asset or asset.org_id != org.id:
        raise HTTPException(status_code=404, detail="Asset not found")

    if asset.faiss_index_id is not None:
        faiss_manager.remove([asset.faiss_index_id])

    asset.is_active = False
    await db.commit()


@router.post("/{asset_id}/verify-watermark")
async def verify_watermark(
    asset_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(get_default_org),
):
    """Verify if an uploaded file contains a valid watermark for this asset."""
    asset = await db.get(Asset, asset_id)
    if not asset or asset.org_id != org.id:
        raise HTTPException(status_code=404, detail="Asset not found")

    if not asset.watermark_id:
        raise HTTPException(status_code=400, detail="Asset has no watermark")

    file_bytes = await file.read()
    result = verify_asset_ownership(file_bytes, asset.watermark_id)

    return {"asset_id": asset_id, "asset_title": asset.title, **result}
