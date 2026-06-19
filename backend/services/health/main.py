"""Health Service — keystroke feature ingest, wearable sync, summary."""

from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from ...shared.config import get_settings
from ...shared.security.hipaa_logger import HIPAAAuditMiddleware
from .routers.keystroke import router as keystroke_router
from .routers.wearable import router as wearable_router
from .routers.summary import router as summary_router
from .routers.assessments import router as assessments_router

settings = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.app_env)
    yield


app = FastAPI(title="NeuroGuard Health Service", version=settings.app_version, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(HIPAAAuditMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(keystroke_router,   prefix="/api/v1/keystroke",   tags=["keystroke"])
app.include_router(wearable_router,    prefix="/api/v1/wearable",    tags=["wearable"])
app.include_router(summary_router,     prefix="/api/v1/health",      tags=["health"])
app.include_router(assessments_router, prefix="/api/v1/assessments", tags=["assessments"])


@app.get("/api/v1/health/ping", include_in_schema=False)
async def health_check():
    return {"status": "ok", "service": "health"}
