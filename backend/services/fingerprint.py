"""
Phase 1 Core: Digital Fingerprinting Service
─────────────────────────────────────────────
Generates perceptual hashes for images and video frames.
Perceptual hashes are robust to:
  - Resizing / compression
  - Color adjustments
  - Minor crops
  - Format conversion (JPEG → PNG → WebP)
"""

import io
import hashlib
from typing import List, Optional, Tuple
import numpy as np
from PIL import Image
import imagehash
import cv2
from loguru import logger
from config import settings


# ─── Image Fingerprinting ─────────────────────────────────────────────────────

def compute_image_hashes(image_input: bytes | str | Image.Image) -> dict:
    """
    Compute multiple perceptual hashes for an image.
    
    Returns:
        {
            "phash": "f8e4...",   # Best for general similarity
            "dhash": "3c90...",   # Good for structural changes
            "ahash": "fff0...",   # Fast, less precise
            "whash": "a1b2...",   # Wavelet — handles noise well
            "md5":   "abc123..."  # Exact match
        }
    """
    if isinstance(image_input, bytes):
        img = Image.open(io.BytesIO(image_input)).convert("RGB")
    elif isinstance(image_input, str):
        img = Image.open(image_input).convert("RGB")
    elif isinstance(image_input, Image.Image):
        img = image_input.convert("RGB")
    else:
        raise ValueError(f"Unsupported image input type: {type(image_input)}")

    hashes = {}
    try:
        hashes["phash"] = str(imagehash.phash(img, hash_size=settings.HASH_SIZE))
        hashes["dhash"] = str(imagehash.dhash(img, hash_size=settings.HASH_SIZE))
        hashes["ahash"] = str(imagehash.average_hash(img, hash_size=settings.HASH_SIZE))
        hashes["whash"] = str(imagehash.whash(img, hash_size=settings.HASH_SIZE))

        # MD5 of raw pixel data for exact-match detection
        raw = img.tobytes()
        hashes["md5"] = hashlib.md5(raw).hexdigest()

    except Exception as e:
        logger.error(f"Hash computation failed: {e}")
        raise

    return hashes


def hash_to_vector(hash_str: str) -> np.ndarray:
    """
    Convert a perceptual hash hex string to a float32 bit vector.
    FAISS uses float32 vectors for distance computation.
    """
    hash_int = int(hash_str, 16)
    bits = []
    for i in range(settings.FAISS_DIM):
        bits.append(float((hash_int >> i) & 1))
    return np.array(bits, dtype=np.float32)


def hamming_distance(hash1: str, hash2: str) -> int:
    """
    Compute Hamming distance between two perceptual hash hex strings.
    Lower = more similar. 0 = identical. >10 = likely different image.
    """
    h1 = imagehash.hex_to_hash(hash1)
    h2 = imagehash.hex_to_hash(hash2)
    return h1 - h2


def similarity_score(hamming_dist: int, max_bits: int = 64) -> float:
    """
    Convert Hamming distance to a 0-100 similarity percentage.
    100 = identical, 0 = completely different.
    """
    return round((1 - hamming_dist / max_bits) * 100, 2)


# ─── Video Fingerprinting ─────────────────────────────────────────────────────

def extract_video_keyframes(
    video_path: str,
    interval_seconds: int = None,
) -> List[Tuple[int, float, Image.Image]]:
    """
    Extract keyframes from video at regular intervals.
    
    Args:
        video_path: Path to video file
        interval_seconds: Extract 1 frame every N seconds (default: from config)
    
    Returns:
        List of (frame_number, timestamp_seconds, PIL.Image)
    """
    interval = interval_seconds or settings.VIDEO_FRAME_INTERVAL
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    logger.info(f"Video: {duration:.1f}s, {fps:.1f} FPS, {total_frames} frames")

    frame_interval = max(1, int(fps * interval))
    keyframes = []
    frame_number = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_number % frame_interval == 0:
            # Convert BGR (OpenCV) → RGB (PIL)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)
            timestamp = frame_number / fps
            keyframes.append((frame_number, timestamp, pil_image))

        frame_number += 1

    cap.release()
    logger.info(f"Extracted {len(keyframes)} keyframes from video")
    return keyframes


def compute_video_fingerprints(video_path: str) -> dict:
    """
    Compute fingerprints for an entire video.
    
    Returns:
        {
            "duration_seconds": 120.5,
            "fps": 30.0,
            "total_frames": 3615,
            "keyframes": [
                {
                    "frame_number": 0,
                    "timestamp_seconds": 0.0,
                    "phash": "f8e4...",
                    "dhash": "3c90...",
                    "vector": [0, 1, 1, ...]
                },
                ...
            ]
        }
    """
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    cap.release()

    keyframes_data = extract_video_keyframes(video_path)

    result = {
        "duration_seconds": round(duration, 2),
        "fps": round(fps, 2),
        "total_frames": total_frames,
        "keyframes": [],
    }

    for frame_num, timestamp, pil_image in keyframes_data:
        try:
            hashes = compute_image_hashes(pil_image)
            result["keyframes"].append({
                "frame_number": frame_num,
                "timestamp_seconds": round(timestamp, 3),
                "phash": hashes["phash"],
                "dhash": hashes["dhash"],
                "ahash": hashes["ahash"],
                "vector": hash_to_vector(hashes["phash"]).tolist(),
            })
        except Exception as e:
            logger.warning(f"Failed to hash frame {frame_num}: {e}")
            continue

    return result


# ─── Batch Processing ─────────────────────────────────────────────────────────

def compute_fingerprint_for_url(image_url: str) -> Optional[dict]:
    """
    Download an image from URL and compute its fingerprint.
    Used by the crawler to fingerprint discovered media.
    """
    import httpx
    try:
        response = httpx.get(image_url, timeout=10, follow_redirects=True)
        response.raise_for_status()
        return compute_image_hashes(response.content)
    except Exception as e:
        logger.warning(f"Failed to fingerprint URL {image_url}: {e}")
        return None


def detect_scene_changes(video_path: str, threshold: float = 30.0) -> List[float]:
    """
    Detect scene change timestamps in a video.
    Useful for identifying clips extracted from a larger broadcast.
    
    Returns list of timestamps (in seconds) where scene changes occur.
    """
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    prev_frame = None
    scene_changes = []
    frame_num = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if prev_frame is not None:
            diff = cv2.absdiff(prev_frame, gray)
            mean_diff = diff.mean()
            if mean_diff > threshold:
                scene_changes.append(round(frame_num / fps, 2))

        prev_frame = gray
        frame_num += 1

    cap.release()
    return scene_changes
