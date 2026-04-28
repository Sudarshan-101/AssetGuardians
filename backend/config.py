from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Digital Asset Protection API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "changeme-use-a-strong-secret-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Default org (used when auth is disabled)
    DEFAULT_ORG_NAME: str = "Default Organization"
    DEFAULT_ORG_EMAIL: str = "admin@assetguard.local"
    DEFAULT_ORG_PASSWORD: str = "changeme"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/dap_db"
    DATABASE_URL_SYNC: str = "postgresql://postgres:password@localhost:5432/dap_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage (local or S3)
    STORAGE_BACKEND: str = "local"   # "local" or "s3"
    UPLOAD_DIR: str = "./uploads"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_BUCKET: Optional[str] = None
    AWS_REGION: str = "us-east-1"

    # FAISS
    FAISS_INDEX_PATH: str = "./faiss_index"
    FAISS_DIM: int = 64              # pHash bit length
    SIMILARITY_THRESHOLD: int = 10  # Hamming distance threshold

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Notifications
    SENDGRID_API_KEY: Optional[str] = None
    ALERT_EMAIL_FROM: str = "alerts@dap-system.com"

    # Fingerprinting
    VIDEO_FRAME_INTERVAL: int = 2   # Extract frame every N seconds
    HASH_SIZE: int = 8              # pHash grid size (8x8 = 64 bits)

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
