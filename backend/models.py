from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime,
    Text, ForeignKey, Enum, JSON, BigInteger
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum
import uuid


def gen_uuid():
    return str(uuid.uuid4())


class AssetType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class ViolationStatus(str, enum.Enum):
    DETECTED = "detected"
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    plan = Column(String(50), default="starter")  # starter, pro, enterprise
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    assets = relationship("Asset", back_populates="organization", cascade="all, delete-orphan")
    violations = relationship("Violation", back_populates="organization")

    def __repr__(self):
        return f"<Organization {self.name}>"


class Asset(Base):
    __tablename__ = "assets"

    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    asset_type = Column(Enum(AssetType), nullable=False)
    original_filename = Column(String(500))
    file_path = Column(String(1000))          # storage path (local or S3 key)
    file_size = Column(BigInteger)             # bytes
    mime_type = Column(String(100))

    # Fingerprints
    phash = Column(String(64))                 # perceptual hash hex
    dhash = Column(String(64))                 # difference hash hex
    ahash = Column(String(64))                 # average hash hex
    whash = Column(String(64))                 # wavelet hash hex
    faiss_index_id = Column(Integer)           # position in FAISS index

    # Video-specific
    duration_seconds = Column(Float, nullable=True)
    frame_count = Column(Integer, nullable=True)

    # Rights
    rights_owner = Column(String(255))
    rights_description = Column(Text)
    is_registered = Column(Boolean, default=False)

    # Watermark
    is_watermarked = Column(Boolean, default=False)
    watermark_id = Column(String(64))          # unique watermark payload

    # Metadata
    extra_meta = Column(JSON, default={})
    tags = Column(JSON, default=[])
    is_active = Column(Boolean, default=True)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization", back_populates="assets")
    violations = relationship("Violation", back_populates="asset")
    frame_hashes = relationship("FrameHash", back_populates="asset", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Asset {self.title}>"


class FrameHash(Base):
    """For video assets — stores hash per extracted keyframe."""
    __tablename__ = "frame_hashes"

    id = Column(String, primary_key=True, default=gen_uuid)
    asset_id = Column(String, ForeignKey("assets.id"), nullable=False)
    frame_number = Column(Integer)
    timestamp_seconds = Column(Float)
    phash = Column(String(64))
    faiss_index_id = Column(Integer)

    asset = relationship("Asset", back_populates="frame_hashes")


class Violation(Base):
    __tablename__ = "violations"

    id = Column(String, primary_key=True, default=gen_uuid)
    asset_id = Column(String, ForeignKey("assets.id"), nullable=False)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)

    # Where it was found
    infringing_url = Column(String(2000), nullable=False)
    platform = Column(String(100))             # twitter, instagram, youtube, web
    infringing_thumbnail_path = Column(String(1000))

    # Match details
    similarity_score = Column(Float)           # 0-100, higher = more similar
    hamming_distance = Column(Integer)         # lower = more similar
    match_type = Column(String(50))            # phash, dhash, watermark
    matched_frame_id = Column(String, ForeignKey("frame_hashes.id"), nullable=True)

    # Status
    status = Column(Enum(ViolationStatus), default=ViolationStatus.DETECTED)
    is_dmca_sent = Column(Boolean, default=False)
    dmca_sent_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text)

    # Timestamps
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    asset = relationship("Asset", back_populates="violations")
    organization = relationship("Organization", back_populates="violations")

    def __repr__(self):
        return f"<Violation {self.platform}: {self.infringing_url[:50]}>"


class ScanJob(Base):
    """Tracks background scan jobs for monitoring."""
    __tablename__ = "scan_jobs"

    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    celery_task_id = Column(String, nullable=True)
    scan_type = Column(String(50))             # full, incremental, single_asset
    status = Column(String(50), default="pending")  # pending, running, done, failed
    assets_scanned = Column(Integer, default=0)
    violations_found = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
