"""Auth Service — JWT issue/refresh, Auth0 integration, MFA."""

import os
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from ...shared.config import get_settings
from ...shared.security.hipaa_logger import HIPAAAuditMiddleware
from .routers.auth import router as auth_router

settings = get_settings()

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.app_env, traces_sample_rate=0.1)
    yield


app = FastAPI(
    title="NeuroGuard Auth Service",
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(HIPAAAuditMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.neuroguard.health", "https://dashboard.neuroguard.health"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])


@app.get("/api/v1/health", include_in_schema=False)
async def health_check():
    return {"status": "ok", "service": "auth", "version": settings.app_version}
