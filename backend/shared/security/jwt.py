"""JWT verification — RS256 (Auth0/production) with HS256 fallback for dev."""

import os
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

_bearer = HTTPBearer()
_AUTH0_DOMAIN  = os.getenv("AUTH0_DOMAIN",  "dev.neuroguard.local")
_AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "https://api.neuroguard.health")
_JWT_SECRET    = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-in-production")
_JWKS_CACHE: Optional[dict] = None


async def _try_rs256(token: str) -> Optional[dict]:
    """Attempt RS256 verification via Auth0 JWKS endpoint. Returns None on failure."""
    if _AUTH0_DOMAIN == "dev.neuroguard.local":
        return None   # skip in dev
    try:
        import httpx
        global _JWKS_CACHE
        if not _JWKS_CACHE:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"https://{_AUTH0_DOMAIN}/.well-known/jwks.json")
                resp.raise_for_status()
                _JWKS_CACHE = resp.json()
        header = jwt.get_unverified_header(token)
        rsa_key = next(
            ({"kty": k["kty"], "kid": k["kid"], "use": k["use"], "n": k["n"], "e": k["e"]}
             for k in _JWKS_CACHE.get("keys", []) if k["kid"] == header.get("kid")),
            None,
        )
        if not rsa_key:
            return None
        return jwt.decode(token, rsa_key, algorithms=["RS256"],
                          audience=_AUTH0_AUDIENCE, issuer=f"https://{_AUTH0_DOMAIN}/")
    except Exception:
        return None


def _try_hs256(token: str) -> Optional[dict]:
    """HS256 verification for dev/local use."""
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=["HS256"],
                          audience=_AUTH0_AUDIENCE, options={"verify_aud": False})
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    token = credentials.credentials

    payload = await _try_rs256(token)
    if payload is None:
        payload = _try_hs256(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload
