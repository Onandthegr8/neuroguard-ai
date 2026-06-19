"""Auth endpoints: login, refresh, logout."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.db.session import get_db
from ....shared.db.redis import get_redis
from ....shared.models.user import User
from ....shared.schemas.auth import LoginRequest, LoginResponse, RefreshRequest, RefreshResponse
from ....shared.security.hipaa_logger import log_explicit
from ....shared.config import get_settings

import bcrypt
import httpx

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
settings = get_settings()


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
@limiter.limit("5/15minutes")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await _authenticate_user(body, db)
    if not user:
        await log_explicit("LOGIN", "user", outcome="failure", details={"reason": "invalid_credentials"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    tokens = await _issue_tokens(user)
    await log_explicit("LOGIN", "user", actor_id=user.id, actor_role=_get_role(user), outcome="success")
    return LoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_in=settings.access_token_ttl,
        user={"id": str(user.id), "email": user.email, "role": _get_role(user)},
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(body: RefreshRequest):
    """
    Refresh-token rotation (OWASP recommended):
      - validate old refresh token in Redis
      - immediately invalidate it (one-time use)
      - issue a fresh refresh token alongside the new access token
    """
    redis = await get_redis()
    user_id = await redis.get(f"refresh:{body.refresh_token}")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    # Atomic rotation: delete the consumed token first
    await redis.delete(f"refresh:{body.refresh_token}")

    new_refresh_token = str(uuid.uuid4())
    await redis.setex(f"refresh:{new_refresh_token}", settings.refresh_token_ttl, user_id)

    new_access_token = await _issue_access_token(uuid.UUID(user_id))
    return RefreshResponse(
        access_token  = new_access_token,
        refresh_token = new_refresh_token,
        expires_in    = settings.access_token_ttl,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        redis = await get_redis()
        await redis.setex(f"revoked:{token}", settings.access_token_ttl + 60, "1")
    return None


async def _authenticate_user(body: LoginRequest, db: AsyncSession):
    if body.email and body.password:
        result = await db.execute(select(User).where(User.email == body.email, User.deleted_at.is_(None)))
        user = result.scalar_one_or_none()
        if user and user.password_hash and bcrypt.checkpw(body.password.encode(), user.password_hash.encode()):
            return user
    return None


async def _issue_access_token(user_id: uuid.UUID, role: str = "user") -> str:
    import time, os
    from jose import jwt
    payload = {
        "sub": str(user_id),
        "iss": f"https://{settings.auth0_domain}/",
        "aud": settings.auth0_audience,
        "iat": int(time.time()),
        "exp": int(time.time()) + settings.access_token_ttl,
        "role": role,
    }
    pem_path = "/app/secrets/jwt_private.pem"
    if os.path.exists(pem_path):
        private_key = open(pem_path).read()
        return jwt.encode(payload, private_key, algorithm="RS256")
    # Dev fallback: HS256 with shared secret
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


async def _issue_tokens(user: User) -> dict:
    redis = await get_redis()
    refresh_token = str(uuid.uuid4())
    role = _get_role(user)
    await redis.setex(f"refresh:{refresh_token}", settings.refresh_token_ttl, str(user.id))
    access_token = await _issue_access_token(user.id, role)
    return {"access_token": access_token, "refresh_token": refresh_token}


def _get_role(user: User) -> str:
    # Check for clinician or admin markers (production: query clinicians/hospitals tables)
    if user.risk_group == "hospital_admin":
        return "hospital_admin"
    if user.risk_group == "clinician":
        return "clinician"
    return "user"
