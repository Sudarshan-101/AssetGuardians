"""
Phase 2: Invisible Watermarking Service
────────────────────────────────────────
Embeds imperceptible watermarks into images and video frames.

Two strategies:
  1. DCT-based (Discrete Cosine Transform) — robust to JPEG compression
  2. LSB (Least Significant Bit)          — fragile, for tamper detection

For MVP we use the `invisible-watermark` library (DCT/DWT).
"""

import io
import hashlib
from typing import Optional, Tuple
import numpy as np
from PIL import Image
from loguru import logger

try:
    from imwatermark import WatermarkEncoder, WatermarkDecoder
    WATERMARK_AVAILABLE = True
except ImportError:
    WATERMARK_AVAILABLE = False
    logger.warning("invisible-watermark not installed — watermarking disabled")


# ─── Watermark ID Generation ──────────────────────────────────────────────────

def generate_watermark_id(asset_id: str, org_id: str) -> str:
    """
    Generate a unique 64-bit watermark payload from asset + org IDs.
    This gets embedded invisibly into the image.
    """
    combined = f"{org_id}:{asset_id}"
    digest = hashlib.sha256(combined.encode()).hexdigest()
    return digest[:16]  # 64-bit hex = 8 bytes


def watermark_id_to_bytes(wm_id: str) -> bytes:
    """Convert 16-char hex watermark ID to 8 bytes."""
    return bytes.fromhex(wm_id)


# ─── Image Watermarking ───────────────────────────────────────────────────────

def embed_watermark_image(
    image_input: bytes | str,
    watermark_id: str,
    method: str = "dwtDct",
) -> Tuple[bytes, str]:
    """
    Embed an invisible watermark into an image.
    
    Args:
        image_input: Image bytes or file path
        watermark_id: 16-char hex string to embed
        method: "dwtDct" (recommended) | "rivaGan" | "dwtDctSvd"
    
    Returns:
        (watermarked_image_bytes, watermark_id)
    """
    if not WATERMARK_AVAILABLE:
        logger.warning("Watermarking skipped — library not available")
        if isinstance(image_input, str):
            with open(image_input, "rb") as f:
                return f.read(), watermark_id
        return image_input, watermark_id

    # Load image
    if isinstance(image_input, bytes):
        img = Image.open(io.BytesIO(image_input)).convert("RGB")
    else:
        img = Image.open(image_input).convert("RGB")

    img_array = np.array(img)

    # Embed watermark
    encoder = WatermarkEncoder()
    wm_bytes = watermark_id.encode("utf-8")[:8]  # 8 bytes max for dwtDct
    encoder.set_watermark("bytes", wm_bytes)

    try:
        encoded = encoder.encode(img_array, method)
        result_img = Image.fromarray(encoded)

        # Return as JPEG bytes
        output = io.BytesIO()
        result_img.save(output, format="JPEG", quality=95)
        return output.getvalue(), watermark_id

    except Exception as e:
        logger.error(f"Watermark embedding failed: {e}")
        # Return original image on failure
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=95)
        return output.getvalue(), watermark_id


def detect_watermark_image(
    image_input: bytes | str,
    method: str = "dwtDct",
) -> Optional[str]:
    """
    Attempt to extract a watermark from an image.
    
    Returns:
        Extracted watermark ID string if found, None otherwise.
    """
    if not WATERMARK_AVAILABLE:
        return None

    if isinstance(image_input, bytes):
        img = Image.open(io.BytesIO(image_input)).convert("RGB")
    else:
        img = Image.open(image_input).convert("RGB")

    img_array = np.array(img)

    try:
        decoder = WatermarkDecoder("bytes", 64)  # 64 bits = 8 bytes
        wm_bytes = decoder.decode(img_array, method)
        wm_str = wm_bytes.decode("utf-8", errors="ignore").strip("\x00")
        if wm_str and len(wm_str) >= 4:
            return wm_str
        return None
    except Exception as e:
        logger.warning(f"Watermark detection failed: {e}")
        return None


# ─── Video Watermarking ───────────────────────────────────────────────────────

def embed_watermark_video(
    video_path: str,
    output_path: str,
    watermark_id: str,
    frame_interval: int = 30,
) -> str:
    """
    Embed watermark into video keyframes using FFmpeg + per-frame processing.
    
    For MVP, we watermark every Nth frame (I-frames proxy).
    In production, use a proper FFmpeg filter pipeline.
    
    Returns: output_path of watermarked video
    """
    import cv2

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    frame_num = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_num % frame_interval == 0:
            # Embed watermark in this frame
            from PIL import Image as PILImage
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil = PILImage.fromarray(rgb)
            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            wm_bytes, _ = embed_watermark_image(buf.getvalue(), watermark_id)
            wm_img = PILImage.open(io.BytesIO(wm_bytes)).convert("RGB")
            frame = cv2.cvtColor(np.array(wm_img), cv2.COLOR_RGB2BGR)

        out.write(frame)
        frame_num += 1

    cap.release()
    out.release()
    logger.info(f"Video watermarked: {frame_num} frames → {output_path}")
    return output_path


# ─── Verification API ─────────────────────────────────────────────────────────

def verify_asset_ownership(
    image_input: bytes | str,
    expected_watermark_id: str,
) -> dict:
    """
    Verify if an image contains the expected watermark.
    
    Returns:
        {
            "verified": True/False,
            "detected_id": "...",
            "expected_id": "...",
            "confidence": "high"/"medium"/"low"
        }
    """
    detected = detect_watermark_image(image_input)
    verified = detected == expected_watermark_id

    # Partial match check
    confidence = "none"
    if verified:
        confidence = "high"
    elif detected and expected_watermark_id and (
        detected[:4] == expected_watermark_id[:4]
    ):
        confidence = "low"

    return {
        "verified": verified,
        "detected_id": detected,
        "expected_id": expected_watermark_id,
        "confidence": confidence,
    }
