"""
Digital Asset Protection — FastAPI Application
───────────────────────────────────────────────
Main entry point. Registers all routers, sets up middleware,
initializes database and FAISS index on startup.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from loguru import logger

from config import settings
from database import init_db, AsyncSessionLocal
from services.faiss_index import faiss_manager


async def _ensure_default_org():
    """Create the default organization on first startup if it doesn't exist."""
    from sqlalchemy import select
    from models import Organization
    from routers.auth import hash_password

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Organization).where(Organization.email == settings.DEFAULT_ORG_EMAIL)
        )
        if result.scalar_one_or_none():
            return

        org = Organization(
            name=settings.DEFAULT_ORG_NAME,
            email=settings.DEFAULT_ORG_EMAIL,
            hashed_password=hash_password(settings.DEFAULT_ORG_PASSWORD),
            plan="pro",
        )
        session.add(org)
        await session.commit()
        logger.info(f"Default org created: {settings.DEFAULT_ORG_NAME} ({settings.DEFAULT_ORG_EMAIL})")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🚀 Starting Digital Asset Protection API...")
    await init_db()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    faiss_dir = os.path.dirname(settings.FAISS_INDEX_PATH) or "."
    os.makedirs(faiss_dir, exist_ok=True)
    await _ensure_default_org()
    logger.info(f"FAISS index ready: {faiss_manager.stats()}")
    logger.info("✅ Startup complete")
    yield
    logger.info("👋 Shutting down...")


# ─── App Initialization ───────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## Digital Asset Protection API

Protect your sports media from unauthorized use.

### Features
- 🔍 **Perceptual Fingerprinting** — pHash, dHash, wHash for images & video
- ⚡ **Sub-millisecond Search** — FAISS vector similarity index
- 🕷️ **Automated Crawling** — Twitter, YouTube, Google Images
- 📋 **DMCA Generation** — One-click takedown notices
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "https://your-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Static Files ─────────────────────────────────────────────────────────────

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.UPLOAD_DIR), name="static")

# ─── Routers ──────────────────────────────────────────────────────────────────

from routers.auth import router as auth_router
from routers.assets import router as assets_router
from routers.search import router as search_router
from routers.violations import router as violations_router

app.include_router(auth_router,      prefix="/api/v1")
app.include_router(assets_router,    prefix="/api/v1")
app.include_router(search_router,    prefix="/api/v1")
app.include_router(violations_router, prefix="/api/v1")

# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "faiss_stats": faiss_manager.stats(),
    }


@app.get("/", tags=["System"])
async def root():
    return {
        "message": "Digital Asset Protection API",
        "docs": "/docs",
        "version": settings.APP_VERSION,
    }

# ─── Global Error Handler ─────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else 4,
    )
