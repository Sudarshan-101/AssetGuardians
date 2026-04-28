"""
Violations Router
─────────────────
Manage detected content violations.

GET    /violations/dashboard  → Dashboard stats      (must be before /{id})
GET    /violations/           → List violations
GET    /violations/{id}       → Get violation detail
PATCH  /violations/{id}       → Update status / notes
POST   /violations/{id}/dmca  → Generate DMCA takedown notice
POST   /violations/scan/trigger → Trigger manual scan
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from loguru import logger
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Violation, ViolationStatus, Organization, Asset, ScanJob
from routers.auth import get_default_org
from schemas import ViolationOut, ViolationUpdate, ViolationListOut, DashboardStats

router = APIRouter(prefix="/violations", tags=["Violations"])


# ── Dashboard must be defined before /{violation_id} to avoid route shadowing ──

@router.get("/dashboard", response_model=DashboardStats)
async def dashboard_stats(
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(get_default_org),
):
    """Aggregate stats for the dashboard overview."""
    total_assets = (await db.execute(
        select(func.count()).where(and_(Asset.org_id == org.id, Asset.is_active == True))
    )).scalar()

    total_violations = (await db.execute(
        select(func.count()).where(Violation.org_id == org.id)
    )).scalar()

    active_violations = (await db.execute(
        select(func.count()).where(
            and_(Violation.org_id == org.id, Violation.status == ViolationStatus.DETECTED)
        )
    )).scalar()

    resolved_violations = (await db.execute(
        select(func.count()).where(
            and_(Violation.org_id == org.id, Violation.status == ViolationStatus.RESOLVED)
        )
    )).scalar()

    recent_q = (await db.execute(
        select(Violation)
        .where(Violation.org_id == org.id)
        .order_by(desc(Violation.detected_at))
        .limit(10)
    )).scalars().all()

    platform_q = (await db.execute(
        select(Violation.platform, func.count())
        .where(Violation.org_id == org.id)
        .group_by(Violation.platform)
    )).all()
    violations_by_platform = {p or "unknown": c for p, c in platform_q}

    type_q = (await db.execute(
        select(Asset.asset_type, func.count())
        .where(and_(Asset.org_id == org.id, Asset.is_active == True))
        .group_by(Asset.asset_type)
    )).all()
    assets_by_type = {str(t.value): c for t, c in type_q}

    # 7-day trend
    trend = []
    for i in range(7):
        day = datetime.utcnow() - timedelta(days=6 - i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59)
        count = (await db.execute(
            select(func.count()).where(
                and_(
                    Violation.org_id == org.id,
                    Violation.detected_at >= day_start,
                    Violation.detected_at <= day_end,
                )
            )
        )).scalar()
        trend.append({"date": day_start.strftime("%b %d"), "count": count})

    return DashboardStats(
        total_assets=total_assets,
        total_violations=total_violations,
        active_violations=active_violations,
        resolved_violations=resolved_violations,
        platforms_detected=list(violations_by_platform.keys()),
        recent_violations=list(recent_q),
        assets_by_type=assets_by_type,
        violations_by_platform=violations_by_platform,
        violations_trend=trend,
    )


@router.get("/", response_model=ViolationListOut)
async def list_violations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[ViolationStatus] = None,
    platform: Optional[str] = None,
    asset_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(get_default_org),
):
    query = select(Violation).where(Violation.org_id == org.id)

    if status:
        query = query.where(Violation.status == status)
    if platform:
        query = query.where(Violation.platform == platform)
    if asset_id:
        query = query.where(Violation.asset_id == asset_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    query = query.order_by(desc(Violation.detected_at)).offset((page - 1) * page_size).limit(page_size)
    results = (await db.execute(query)).scalars().all()

    return ViolationListOut(items=list(results), total=total, page=page, page_size=page_size)


# ── Scan trigger before /{violation_id} to avoid shadowing ───────────────────

@router.post("/scan/trigger")
async def trigger_scan(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(get_default_org),
):
    """Manually trigger a scan for the organization."""
    job = ScanJob(org_id=org.id, scan_type="manual", status="pending")
    db.add(job)
    await db.commit()
    await db.refresh(job)

    try:
        from crawler.tasks import run_full_scan
        task = run_full_scan.delay(org_id=org.id, scan_job_id=job.id)
        job.celery_task_id = task.id
        await db.commit()
    except Exception as e:
        logger.warning(f"Celery not available, scan queued: {e}")

    return {"scan_job_id": job.id, "status": "triggered"}


@router.get("/{violation_id}", response_model=ViolationOut)
async def get_violation(
    violation_id: str,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(get_default_org),
):
    v = await db.get(Violation, violation_id)
    if not v or v.org_id != org.id:
        raise HTTPException(status_code=404, detail="Violation not found")
    return v


@router.patch("/{violation_id}", response_model=ViolationOut)
async def update_violation(
    violation_id: str,
    payload: ViolationUpdate,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(get_default_org),
):
    v = await db.get(Violation, violation_id)
    if not v or v.org_id != org.id:
        raise HTTPException(status_code=404, detail="Violation not found")

    if payload.status:
        v.status = payload.status
        if payload.status == ViolationStatus.RESOLVED:
            v.resolved_at = datetime.utcnow()
    if payload.notes is not None:
        v.notes = payload.notes

    await db.commit()
    await db.refresh(v)
    return v


@router.post("/{violation_id}/dmca")
async def generate_dmca_notice(
    violation_id: str,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(get_default_org),
):
    """Generate a DMCA takedown notice for a violation."""
    v = await db.get(Violation, violation_id)
    if not v or v.org_id != org.id:
        raise HTTPException(status_code=404, detail="Violation not found")

    asset = await db.get(Asset, v.asset_id)

    notice_text = f"""DIGITAL MILLENNIUM COPYRIGHT ACT (DMCA) TAKEDOWN NOTICE

Date: {datetime.utcnow().strftime("%B %d, %Y")}

To: Platform Trust & Safety / DMCA Agent

I. IDENTIFICATION OF COPYRIGHTED WORK:
Title: {asset.title if asset else "Protected Content"}
Rights Owner: {asset.rights_owner if asset else org.name}
Organization: {org.name}

II. IDENTIFICATION OF INFRINGING MATERIAL:
URL: {v.infringing_url}
Platform: {v.platform}
Detected: {v.detected_at.strftime("%B %d, %Y at %H:%M UTC")}

III. STATEMENT OF GOOD FAITH:
I have a good faith belief that the use of the described material in the
manner complained of is not authorized by the copyright owner, its agent,
or the law.

IV. STATEMENT OF ACCURACY:
The information in this notification is accurate. Under penalty of perjury,
I am authorized to act on behalf of the copyright owner.

V. CONTACT:
{org.name}
{org.email}

Signature: ___________________________
Date: {datetime.utcnow().strftime("%B %d, %Y")}
"""

    v.is_dmca_sent = True
    v.dmca_sent_at = datetime.utcnow()
    await db.commit()

    return {
        "violation_id": violation_id,
        "dmca_notice": notice_text,
        "generated_at": datetime.utcnow().isoformat(),
    }
