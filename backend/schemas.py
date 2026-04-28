from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from models import AssetType, ViolationStatus


# ─── Auth ────────────────────────────────────────────────────────────────────

class OrgCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class OrgLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OrgOut(BaseModel):
    id: str
    name: str
    email: str
    plan: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Assets ──────────────────────────────────────────────────────────────────

class AssetCreate(BaseModel):
    title: str
    description: Optional[str] = None
    rights_owner: Optional[str] = None
    rights_description: Optional[str] = None
    tags: Optional[List[str]] = []


class AssetOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    asset_type: AssetType
    original_filename: Optional[str]
    file_size: Optional[int]
    mime_type: Optional[str]
    phash: Optional[str]
    dhash: Optional[str]
    duration_seconds: Optional[float]
    frame_count: Optional[int]
    is_watermarked: bool
    is_registered: bool
    rights_owner: Optional[str]
    tags: Optional[List[str]]
    registered_at: datetime
    violation_count: Optional[int] = 0

    model_config = {"from_attributes": True}


class AssetListOut(BaseModel):
    items: List[AssetOut]
    total: int
    page: int
    page_size: int


# ─── Fingerprint Search ───────────────────────────────────────────────────────

class FingerprintSearchResult(BaseModel):
    asset_id: str
    asset_title: str
    similarity_score: float
    hamming_distance: int
    match_type: str
    asset_type: AssetType
    registered_at: datetime


class SearchResponse(BaseModel):
    query_hash: str
    matches: List[FingerprintSearchResult]
    search_time_ms: float
    threshold_used: int


# ─── Violations ───────────────────────────────────────────────────────────────

class ViolationOut(BaseModel):
    id: str
    asset_id: str
    infringing_url: str
    platform: Optional[str]
    similarity_score: Optional[float]
    hamming_distance: Optional[int]
    match_type: Optional[str]
    status: ViolationStatus
    is_dmca_sent: bool
    detected_at: datetime
    resolved_at: Optional[datetime]
    notes: Optional[str]

    model_config = {"from_attributes": True}


class ViolationUpdate(BaseModel):
    status: Optional[ViolationStatus] = None
    notes: Optional[str] = None


class ViolationListOut(BaseModel):
    items: List[ViolationOut]
    total: int
    page: int
    page_size: int


# ─── Dashboard Stats ──────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_assets: int
    total_violations: int
    active_violations: int
    resolved_violations: int
    platforms_detected: List[str]
    recent_violations: List[ViolationOut]
    assets_by_type: dict
    violations_by_platform: dict
    violations_trend: List[dict]   # [{date, count}]


# ─── DMCA ─────────────────────────────────────────────────────────────────────

class DMCANoticeRequest(BaseModel):
    violation_id: str
    complainant_name: str
    complainant_address: str
    complainant_email: EmailStr
    signature: str


class DMCANoticeOut(BaseModel):
    violation_id: str
    pdf_path: str
    generated_at: datetime
