"""
Authentication Router
─────────────────────
JWT-based auth kept for optional use.
In no-auth mode all routes use get_default_org instead.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt
from passlib.context import CryptContext
from loguru import logger

from database import get_db
from models import Organization
from schemas import OrgCreate, Token, OrgOut
from config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_default_org(db: AsyncSession = Depends(get_db)) -> Organization:
    """
    Dependency used by all routes in no-auth mode.
    Returns the default organization, creating it on first run if needed.
    """
    result = await db.execute(
        select(Organization).where(Organization.email == settings.DEFAULT_ORG_EMAIL)
    )
    org = result.scalar_one_or_none()
    if org:
        return org

    # Auto-create default org on first request
    org = Organization(
        name=settings.DEFAULT_ORG_NAME,
        email=settings.DEFAULT_ORG_EMAIL,
        hashed_password=hash_password(settings.DEFAULT_ORG_PASSWORD),
        plan="pro",
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    logger.info(f"Auto-created default org: {org.name} ({org.email})")
    return org


async def get_current_org(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    """JWT auth dependency — kept for optional/future use."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        org_id: str = payload.get("sub")
        if not org_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    org = await db.get(Organization, org_id)
    if not org or not org.is_active:
        raise credentials_exception
    return org


@router.post("/register", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
async def register(payload: OrgCreate, db: AsyncSession = Depends(get_db)):
    """Register a new organization."""
    existing = await db.execute(
        select(Organization).where(Organization.email == payload.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    org = Organization(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    logger.info(f"New org registered: {org.name} ({org.email})")
    return org


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Login and receive a JWT access token."""
    result = await db.execute(
        select(Organization).where(Organization.email == form_data.username)
    )
    org = result.scalar_one_or_none()

    if not org or not verify_password(form_data.password, org.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token({"sub": org.id, "name": org.name})
    logger.info(f"Login: {org.email}")
    return Token(access_token=token)


@router.get("/me", response_model=OrgOut)
async def me(org: Organization = Depends(get_current_org)):
    return org
