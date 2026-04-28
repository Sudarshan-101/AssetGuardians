"""
Search Router
─────────────
Upload an image → find matching registered assets.

POST /search/fingerprint  → Upload file, get similarity matches
POST /search/url          → Provide URL, get similarity matches
GET  /search/stats        → FAISS index statistics
"""

import time
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models import Asset, Organization
from routers.auth import get_default_org
from schemas import SearchResponse, FingerprintSearchResult
from services.faiss_index import faiss_manager
from services.fingerprint import compute_image_hashes, hash_to_vector, compute_fingerprint_for_url

router = APIRouter(prefix="/search", tags=["Search"])


async def _run_search(phash: str, db: AsyncSession, org: Organization) -> SearchResponse:
    """Core search logic — find matches in FAISS and enrich with DB data."""
    start = time.time()
    vec = hash_to_vector(phash)

    raw_matches = faiss_manager.search(
        query_vector=vec,
        top_k=20,
        threshold=settings.SIMILARITY_THRESHOLD,
    )

    enriched = []
    for match in raw_matches:
        asset = await db.get(Asset, match["asset_id"])
        if not asset or not asset.is_active:
            continue
        if asset.org_id != org.id:
            continue

        enriched.append(FingerprintSearchResult(
            asset_id=asset.id,
            asset_title=asset.title,
            similarity_score=match["similarity"],
            hamming_distance=match["hamming_dist"],
            match_type="phash",
            asset_type=asset.asset_type,
            registered_at=asset.registered_at,
        ))

    elapsed_ms = (time.time() - start) * 1000
    return SearchResponse(
        query_hash=phash,
        matches=enriched,
        search_time_ms=round(elapsed_ms, 2),
        threshold_used=settings.SIMILARITY_THRESHOLD,
    )


@router.post("/fingerprint", response_model=SearchResponse)
async def search_by_fingerprint(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(get_default_org),
):
    """Upload an image and find matching registered assets."""
    file_bytes = await file.read()
    try:
        hashes = compute_image_hashes(file_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Cannot process image: {e}")

    logger.info(f"Fingerprint search: phash={hashes['phash']}")
    return await _run_search(hashes["phash"], db, org)


@router.post("/url", response_model=SearchResponse)
async def search_by_url(
    url: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(get_default_org),
):
    """Provide a public image URL and find matching registered assets."""
    hashes = compute_fingerprint_for_url(url)
    if not hashes:
        raise HTTPException(status_code=422, detail="Cannot download or fingerprint the provided URL")

    logger.info(f"URL search: {url} → phash={hashes['phash']}")
    return await _run_search(hashes["phash"], db, org)


@router.get("/stats")
async def index_stats(org: Organization = Depends(get_default_org)):
    """Get FAISS index statistics."""
    return faiss_manager.stats()
