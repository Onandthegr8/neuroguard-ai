"""Federated Service — Flower server coordinator, DP accounting, update acceptance."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ...shared.config import get_settings
from ...shared.security.hipaa_logger import HIPAAAuditMiddleware
from .routers.federated import router as fl_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Flower server is started as a separate process (ml/federated/server.py)
    # This service handles the REST coordination API only
    yield


app = FastAPI(title="NeuroGuard Federated Service", version=settings.app_version, lifespan=lifespan)
app.add_middleware(HIPAAAuditMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(fl_router, prefix="/api/v1/federated", tags=["federated"])


@app.get("/api/v1/health/ping", include_in_schema=False)
async def health_check():
    return {"status": "ok", "service": "federated"}
