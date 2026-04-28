"""
Storage Service
───────────────
Abstracts file storage between local filesystem and AWS S3.
Swap STORAGE_BACKEND in .env to switch.
"""

import os
import uuid
import aiofiles
from pathlib import Path
from loguru import logger
from config import settings


def _get_storage_key(filename: str, org_id: str) -> str:
    """Generate a unique storage key / path for a file."""
    ext = Path(filename).suffix.lower()
    unique_id = str(uuid.uuid4())
    return f"assets/{org_id}/{unique_id}{ext}"


async def save_file(
    file_bytes: bytes,
    original_filename: str,
    org_id: str,
) -> str:
    """
    Save file to configured storage backend.
    Returns the storage path/key.
    """
    key = _get_storage_key(original_filename, org_id)

    if settings.STORAGE_BACKEND == "s3":
        return await _save_to_s3(file_bytes, key)
    else:
        return await _save_locally(file_bytes, key)


async def _save_locally(file_bytes: bytes, key: str) -> str:
    """Save file to local filesystem."""
    full_path = Path(settings.UPLOAD_DIR) / key
    full_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(full_path, "wb") as f:
        await f.write(file_bytes)

    logger.debug(f"Saved file locally: {full_path}")
    return str(full_path)


async def _save_to_s3(file_bytes: bytes, key: str) -> str:
    """Save file to AWS S3."""
    import boto3
    from botocore.exceptions import ClientError

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    try:
        s3_client.put_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=key,
            Body=file_bytes,
        )
        logger.debug(f"Uploaded to S3: s3://{settings.AWS_S3_BUCKET}/{key}")
        return f"s3://{settings.AWS_S3_BUCKET}/{key}"
    except ClientError as e:
        logger.error(f"S3 upload failed: {e}")
        raise


async def read_file(file_path: str) -> bytes:
    """Read a file from configured storage backend."""
    if file_path.startswith("s3://"):
        return await _read_from_s3(file_path)
    else:
        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()


async def _read_from_s3(s3_url: str) -> bytes:
    import boto3
    parts = s3_url.replace("s3://", "").split("/", 1)
    bucket, key = parts[0], parts[1]
    s3_client = boto3.client("s3")
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


async def delete_file(file_path: str):
    """Delete file from storage."""
    if file_path.startswith("s3://"):
        import boto3
        parts = file_path.replace("s3://", "").split("/", 1)
        bucket, key = parts[0], parts[1]
        boto3.client("s3").delete_object(Bucket=bucket, Key=key)
    else:
        try:
            os.remove(file_path)
        except FileNotFoundError:
            pass


def get_public_url(file_path: str) -> str:
    """Get a publicly accessible URL for a file (for thumbnails, etc.)."""
    if file_path.startswith("s3://"):
        parts = file_path.replace("s3://", "").split("/", 1)
        return f"https://{parts[0]}.s3.amazonaws.com/{parts[1]}"
    return f"/static/{file_path.replace(settings.UPLOAD_DIR, '').lstrip('/')}"
