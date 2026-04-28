"""
Phase 3: Web Crawler & Violation Detection
──────────────────────────────────────────
Crawls major platforms to find unauthorized use of registered assets.

Platforms:
  - Twitter/X   (v2 API)
  - YouTube     (Data API v3)
  - Google      (Custom Search API)

Architecture:
  Celery tasks run periodically → download media → fingerprint →
  query FAISS → if match found → create Violation record → alert org
"""

import asyncio
import os
from datetime import datetime
from typing import List, Optional

import aiohttp
from celery import Celery
from loguru import logger

from config import settings
from services.faiss_index import faiss_manager
from services.fingerprint import compute_fingerprint_for_url, hash_to_vector

# ─── Celery App ───────────────────────────────────────────────────────────────

celery_app = Celery("dap_crawler", broker=settings.CELERY_BROKER_URL)
celery_app.conf.result_backend = settings.CELERY_RESULT_BACKEND
celery_app.conf.beat_schedule = {
    "scan-every-30-min": {
        "task": "crawler.tasks.run_full_scan",
        "schedule": 1800.0,
    },
}

# Platform API keys (from environment / .env)
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")
YOUTUBE_API_KEY      = os.getenv("YOUTUBE_API_KEY", "")
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_SEARCH_CX      = os.getenv("GOOGLE_SEARCH_CX", "")


# ─── Platform Crawlers ────────────────────────────────────────────────────────

class TwitterCrawler:
    """Crawls recent media tweets using Twitter v2 API."""

    BASE_URL = "https://api.twitter.com/2"

    def __init__(self):
        self.headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}

    async def search_recent_media(
        self,
        query: str = "sports -is:retweet has:media",
        max_results: int = 100,
    ) -> List[dict]:
        if not TWITTER_BEARER_TOKEN:
            logger.warning("Twitter Bearer Token not configured — skipping")
            return []

        params = {
            "query": query,
            "max_results": min(max_results, 100),
            "expansions": "attachments.media_keys",
            "media.fields": "url,preview_image_url,type",
            "tweet.fields": "author_id,created_at",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/tweets/search/recent",
                    headers=self.headers,
                    params=params,
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"Twitter API error: {resp.status}")
                        return []

                    data = await resp.json()
                    media_map = {
                        m["media_key"]: m
                        for m in data.get("includes", {}).get("media", [])
                    }
                    items = []
                    for tweet in data.get("data", []):
                        for mk in tweet.get("attachments", {}).get("media_keys", []):
                            media = media_map.get(mk)
                            if media and media.get("url"):
                                items.append({
                                    "url": media["url"],
                                    "platform": "twitter",
                                    "source_id": tweet.get("id"),
                                    "source_url": f"https://twitter.com/i/web/status/{tweet.get('id')}",
                                })
                    logger.info(f"Twitter: found {len(items)} media items")
                    return items
        except Exception as e:
            logger.error(f"Twitter crawl error: {e}")
            return []


class YouTubeCrawler:
    """Searches recent YouTube uploads for matching thumbnails."""

    BASE_URL = "https://www.googleapis.com/youtube/v3"

    async def search_recent_uploads(
        self,
        query: str = "sports highlights",
        max_results: int = 50,
    ) -> List[dict]:
        if not YOUTUBE_API_KEY:
            logger.warning("YouTube API key not configured — skipping")
            return []

        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": "date",
            "maxResults": max_results,
            "key": YOUTUBE_API_KEY,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}/search", params=params) as resp:
                    data = await resp.json()
                    items = []
                    for item in data.get("items", []):
                        video_id = item["id"]["videoId"]
                        thumb = item["snippet"]["thumbnails"].get("high", {}).get("url")
                        if thumb:
                            items.append({
                                "url": thumb,
                                "platform": "youtube",
                                "source_id": video_id,
                                "source_url": f"https://youtube.com/watch?v={video_id}",
                            })
                    logger.info(f"YouTube: found {len(items)} thumbnails")
                    return items
        except Exception as e:
            logger.error(f"YouTube crawl error: {e}")
            return []


class GoogleImagesCrawler:
    """Uses Google Custom Search API to find images on the web."""

    BASE_URL = "https://www.googleapis.com/customsearch/v1"

    async def search_images(self, query: str, num: int = 10) -> List[dict]:
        if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_CX:
            return []

        params = {
            "q": query,
            "cx": GOOGLE_SEARCH_CX,
            "key": GOOGLE_SEARCH_API_KEY,
            "searchType": "image",
            "num": min(num, 10),
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.BASE_URL, params=params) as resp:
                    data = await resp.json()
                    return [
                        {
                            "url": item.get("link"),
                            "platform": "web",
                            "source_url": item.get("image", {}).get("contextLink"),
                            "source_id": None,
                        }
                        for item in data.get("items", [])
                        if item.get("link")
                    ]
        except Exception as e:
            logger.error(f"Google Images crawl error: {e}")
            return []


# ─── Violation Detector ───────────────────────────────────────────────────────

class ViolationDetector:
    """Given a media URL, check if it matches any registered asset in FAISS."""

    def check_url(self, media_url: str) -> Optional[dict]:
        hashes = compute_fingerprint_for_url(media_url)
        if not hashes:
            return None

        vec = hash_to_vector(hashes["phash"])
        matches = faiss_manager.search(
            query_vector=vec,
            top_k=5,
            threshold=settings.SIMILARITY_THRESHOLD,
        )

        if matches:
            best = matches[0]
            logger.warning(
                f"VIOLATION: {media_url} → asset {best['asset_id']} "
                f"(similarity={best['similarity']}%, hamming={best['hamming_dist']})"
            )
            return {
                "infringing_url": media_url,
                "asset_id": best["asset_id"],
                "frame_id": best.get("frame_id"),
                "similarity_score": best["similarity"],
                "hamming_distance": best["hamming_dist"],
                "match_type": "phash",
            }
        return None


detector = ViolationDetector()


# ─── Celery Tasks ─────────────────────────────────────────────────────────────

@celery_app.task(name="crawler.tasks.run_full_scan", bind=True, max_retries=3)
def run_full_scan(self, org_id: str = None, scan_job_id: str = None):
    """
    Full scan: crawl all configured platforms and detect violations.
    Runs every 30 min on schedule or on-demand.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from models import Violation, ScanJob, Asset

    engine = create_engine(settings.DATABASE_URL_SYNC)
    Session = sessionmaker(bind=engine)
    session = Session()

    violations_found = 0
    assets_scanned = 0

    try:
        if scan_job_id:
            job = session.get(ScanJob, scan_job_id)
            if job:
                job.status = "running"
                session.commit()

        # Gather media from all platforms using a fresh event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            twitter = TwitterCrawler()
            youtube = YouTubeCrawler()
            results = loop.run_until_complete(asyncio.gather(
                twitter.search_recent_media(),
                youtube.search_recent_uploads(),
            ))
        finally:
            loop.close()

        all_media = [item for platform_items in results for item in platform_items]
        logger.info(f"Total media items to check: {len(all_media)}")

        for item in all_media:
            if not item.get("url"):
                continue

            assets_scanned += 1
            match = detector.check_url(item["url"])

            if match:
                # Deduplicate — don't create a second violation for the same URL+asset
                existing = session.query(Violation).filter_by(
                    infringing_url=item.get("source_url") or item["url"],
                    asset_id=match["asset_id"],
                ).first()

                if not existing:
                    asset = session.get(Asset, match["asset_id"])
                    violation = Violation(
                        asset_id=match["asset_id"],
                        org_id=asset.org_id if asset else org_id,
                        infringing_url=item.get("source_url") or item["url"],
                        platform=item.get("platform"),
                        similarity_score=match["similarity_score"],
                        hamming_distance=match["hamming_distance"],
                        match_type=match["match_type"],
                    )
                    session.add(violation)
                    session.commit()
                    violations_found += 1
                    send_violation_alert.delay(violation.id)

        # Update scan job status
        if scan_job_id:
            job = session.get(ScanJob, scan_job_id)
            if job:
                job.status = "done"
                job.assets_scanned = assets_scanned
                job.violations_found = violations_found
                job.completed_at = datetime.utcnow()
                session.commit()

        logger.info(f"Scan complete: {assets_scanned} checked, {violations_found} new violations")

    except Exception as e:
        logger.error(f"Scan failed: {e}")
        if scan_job_id:
            try:
                job = session.get(ScanJob, scan_job_id)
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    session.commit()
            except Exception:
                pass
        raise self.retry(exc=e, countdown=60)
    finally:
        session.close()
        engine.dispose()


@celery_app.task(name="crawler.tasks.send_violation_alert")
def send_violation_alert(violation_id: str):
    """Send an email alert when a violation is detected."""
    if not settings.SENDGRID_API_KEY:
        logger.warning("SendGrid not configured — skipping email alert")
        return

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, joinedload
    from models import Violation

    engine = create_engine(settings.DATABASE_URL_SYNC)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Eager-load relationships to avoid lazy-load issues outside async context
        violation = (
            session.query(Violation)
            .options(joinedload(Violation.asset), joinedload(Violation.organization))
            .filter(Violation.id == violation_id)
            .first()
        )
        if not violation or not violation.organization:
            return

        import sendgrid
        from sendgrid.helpers.mail import Mail

        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        message = Mail(
            from_email=settings.ALERT_EMAIL_FROM,
            to_emails=violation.organization.email,
            subject=f"⚠️ Unauthorized Content Detected — {violation.platform}",
            html_content=f"""
            <h2>Potential Content Violation Detected</h2>
            <p><strong>Asset:</strong> {violation.asset.title if violation.asset else 'Unknown'}</p>
            <p><strong>Platform:</strong> {violation.platform}</p>
            <p><strong>Infringing URL:</strong>
               <a href="{violation.infringing_url}">{violation.infringing_url}</a></p>
            <p><strong>Similarity:</strong> {violation.similarity_score:.1f}%</p>
            <p><strong>Detected at:</strong> {violation.detected_at}</p>
            """,
        )
        sg.send(message)
        logger.info(f"Alert sent for violation {violation_id}")

    except Exception as e:
        logger.error(f"Failed to send alert for {violation_id}: {e}")
    finally:
        session.close()
        engine.dispose()
