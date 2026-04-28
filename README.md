# AssetGuard — Digital Asset Protection System

Protect your sports media (images, video) from unauthorized use across the web.
Upload your content → it gets fingerprinted → the crawler detects copies → you get alerted and can send DMCA notices.

---

## How It Works

### The Pipeline

```
You upload media
       ↓
Perceptual fingerprint computed (pHash, dHash, aHash, wHash)
       ↓
Fingerprint stored in PostgreSQL + FAISS vector index
       ↓
Celery crawler scans Twitter, YouTube, Google Images every 30 min
       ↓
Each discovered media item is fingerprinted and compared via FAISS
       ↓
Hamming distance ≤ 10 → Violation recorded → Email alert sent
       ↓
You review violations in the dashboard → generate DMCA notice in one click
```

### Perceptual Hashing

Unlike exact MD5 matching, perceptual hashes survive:
- JPEG re-compression
- Resizing / downscaling
- Slight colour adjustments
- Screenshot crops
- Format conversion (MP4 → WebM, PNG → JPEG)

Four hash types are computed per asset:

| Hash | Best for |
|------|----------|
| `pHash` | General similarity — used for FAISS indexing |
| `dHash` | Structural / edge changes |
| `aHash` | Fast rough matching |
| `wHash` | Noise-resistant (wavelet) |

### FAISS Similarity Search

All pHash vectors (64-bit) are stored in a FAISS `IndexFlatL2`. When the crawler finds a new image, it computes its pHash and runs a nearest-neighbour search in milliseconds across millions of indexed hashes.

**Hamming distance thresholds:**
- `0` — identical image
- `1–5` — near-identical (re-compressed, tiny crop)
- `6–10` — strong match (resized, colour-adjusted)
- `> 10` — likely different image (default threshold: `10`)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Browser  →  React SPA (Vite)  →  nginx (port 3000)    │
└────────────────────────┬────────────────────────────────┘
                         │ /api/v1/...
┌────────────────────────▼────────────────────────────────┐
│  FastAPI backend (port 8000)                            │
│  ├── /assets     → upload, list, delete                 │
│  ├── /search     → fingerprint match                    │
│  ├── /violations → list, update, DMCA                  │
│  └── /auth       → register, login (optional)          │
└────────┬──────────────┬───────────────┬────────────────┘
         │              │               │
    PostgreSQL        FAISS           Redis
    (metadata)      (vectors)       (Celery broker)
                                        │
                               Celery Worker
                               └── crawler/tasks.py
                                   ├── TwitterCrawler
                                   ├── YouTubeCrawler
                                   └── GoogleImagesCrawler
```

---

## Quick Start (Docker — recommended)

### 1. Clone / unzip and configure

```bash
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY and DEFAULT_ORG_PASSWORD
```

### 2. Start everything

```bash
docker compose up --build
```

This starts:
- `postgres` — database
- `redis` — Celery broker
- `backend` — FastAPI on port 8000
- `celery_worker` — background scan worker
- `celery_beat` — scan scheduler (every 30 min)
- `frontend` — React UI on port 3000

### 3. Open the app

```
http://localhost:3000
```

No login required. The default organisation is auto-created on first startup.

### 4. API docs

```
http://localhost:8000/docs
```

---

## Local Development (without Docker)

### Backend

```bash
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env   # edit DATABASE_URL to point to your local postgres

# Start postgres + redis (e.g. via homebrew or docker)
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:15-alpine
docker run -d -p 6379:6379 redis:7-alpine

# Run the API
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000/api/v1 npm run dev
# Opens at http://localhost:5173
```

### Celery worker (optional — only needed for automated scanning)

```bash
cd backend
celery -A crawler.tasks worker --loglevel=info
celery -A crawler.tasks beat --loglevel=info   # scheduler
```

---

## Configuration (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `changeme-...` | JWT signing secret — **change this** |
| `DEFAULT_ORG_NAME` | `My Organization` | Name of the auto-created org |
| `DEFAULT_ORG_EMAIL` | `admin@assetguard.local` | Email of the auto-created org |
| `DEFAULT_ORG_PASSWORD` | `changeme` | Password (used only for JWT login via `/api/v1/auth/login`) |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async DB URL for FastAPI |
| `DATABASE_URL_SYNC` | `postgresql://...` | Sync DB URL for Celery tasks |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `SIMILARITY_THRESHOLD` | `10` | Max Hamming distance for a match (0–64) |
| `STORAGE_BACKEND` | `local` | `local` or `s3` |
| `UPLOAD_DIR` | `./uploads` | Where files are stored (local mode) |
| `TWITTER_BEARER_TOKEN` | _(empty)_ | Twitter v2 API — crawler skips if not set |
| `YOUTUBE_API_KEY` | _(empty)_ | YouTube Data API v3 — optional |
| `GOOGLE_SEARCH_API_KEY` | _(empty)_ | Google Custom Search — optional |
| `SENDGRID_API_KEY` | _(empty)_ | Email alerts — optional |

---

## API Endpoints

### Assets

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/assets/upload` | Register new asset (multipart form) |
| `GET` | `/api/v1/assets/` | List assets (paginated) |
| `GET` | `/api/v1/assets/{id}` | Get single asset |
| `DELETE` | `/api/v1/assets/{id}` | Remove asset |

**Upload form fields:**
- `file` — image or video (JPEG, PNG, WebP, MP4, MOV, etc.)
- `title` — required
- `description` — optional
- `rights_owner` — optional (defaults to org name)
- `tags` — comma-separated string

### Search

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/search/fingerprint` | Upload image → find matches |
| `POST` | `/api/v1/search/url` | Provide URL → find matches |
| `GET` | `/api/v1/search/stats` | FAISS index statistics |

### Violations

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/violations/dashboard` | Dashboard stats + trend |
| `GET` | `/api/v1/violations/` | List violations (filterable) |
| `GET` | `/api/v1/violations/{id}` | Get violation detail |
| `PATCH` | `/api/v1/violations/{id}` | Update status / notes |
| `POST` | `/api/v1/violations/{id}/dmca` | Generate DMCA notice text |
| `POST` | `/api/v1/violations/scan/trigger` | Trigger manual scan |

### Auth (optional — app works without logging in)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/auth/register` | Create a new org |
| `POST` | `/api/v1/auth/login` | Get JWT token |
| `GET` | `/api/v1/auth/me` | Current org info |

---

## Frontend Pages

| Page | Route | Description |
|------|-------|-------------|
| Dashboard | default | Stats cards, violations trend chart, recent violations |
| Assets | Assets nav | Grid of registered assets, upload modal |
| Violations | Violations nav | Filterable table, status updates, DMCA button |
| Search | Search nav | Upload an image or enter a URL to find matches |

---

## Supported File Types

**Images:** JPEG, PNG, WebP, GIF, BMP (up to 500 MB)

**Videos:** MP4, MPEG, QuickTime, AVI, WebM (up to 500 MB)

For videos, one keyframe is extracted every 2 seconds (configurable via `VIDEO_FRAME_INTERVAL`). Each keyframe is fingerprinted independently, so even short clips extracted from a longer video are detected.

---

## Violation Statuses

| Status | Meaning |
|--------|---------|
| `detected` | Newly found by crawler — needs review |
| `confirmed` | Verified as a real infringement |
| `disputed` | Contested — under review |
| `resolved` | Takedown successful / content removed |
| `false_positive` | Not actually an infringement |

---

## Troubleshooting

**App opens but shows no data**
- Check backend is running: `http://localhost:8000/health`
- Check CORS: frontend must be on port 3000 or 5173

**Upload fails with 413**
- nginx `client_max_body_size` is set to 510MB — if behind another proxy, increase that too

**Crawler not running**
- Celery worker must be running: `celery -A crawler.tasks worker`
- Platform API keys must be set in `.env` — crawler skips unconfigured platforms silently

**bcrypt / passlib errors**
- Requirements pin `bcrypt==4.0.1` which is compatible with passlib 1.7.4
- Do not upgrade bcrypt past 4.0.x without testing

**FAISS index errors on restart**
- Index files are at `FAISS_INDEX_PATH` (default `./faiss_index/index`)
- Delete `index` and `index.map` files to reset — assets remain in the database but will need re-indexing

---

## Project Structure

```
digital-asset-protection-clean/
├── backend/
│   ├── main.py               # FastAPI app + startup
│   ├── config.py             # All settings (from .env)
│   ├── database.py           # SQLAlchemy async engine
│   ├── models.py             # Organization, Asset, Violation, ScanJob
│   ├── schemas.py            # Pydantic request/response models
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── routers/
│   │   ├── auth.py           # JWT auth + get_default_org dependency
│   │   ├── assets.py         # Upload, list, delete
│   │   ├── violations.py     # List, update, DMCA, dashboard
│   │   └── search.py         # Fingerprint + URL search
│   ├── services/
│   │   ├── fingerprint.py    # pHash/dHash/aHash/wHash computation
│   │   ├── faiss_index.py    # FAISS vector index manager
│   │   ├── storage.py        # Local / S3 file storage
│   │   └── watermark.py      # DCT invisible watermarking
│   └── crawler/
│       └── tasks.py          # Celery tasks: scan, alert
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # Shell + sidebar navigation
│   │   ├── main.jsx          # React entry point
│   │   └── pages/
│   │       ├── Dashboard.jsx
│   │       ├── Assets.jsx
│   │       ├── Violations.jsx
│   │       └── SearchPage.jsx
│   ├── nginx.conf            # Serves SPA + proxies /api/ to backend
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
└── .env.example
```
