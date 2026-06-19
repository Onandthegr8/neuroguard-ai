"""User Service — registration, consent management, profile, patient timeline."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ...shared.config import get_settings
from ...shared.security.hipaa_logger import HIPAAAuditMiddleware
from .routers.user import router as user_router
from .routers.patients import router as patients_router
from .routers.gdpr import router as gdpr_router
from .routers.analytics import router as analytics_router

settings = get_settings()

app = FastAPI(title="NeuroGuard User Service", version=settings.app_version)
app.add_middleware(HIPAAAuditMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(user_router, prefix="/api/v1/user", tags=["user"])
app.include_router(gdpr_router, prefix="/api/v1/user", tags=["gdpr"])
app.include_router(patients_router, prefix="/api/v1", tags=["patients"])
app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["analytics"])


@app.get("/api/v1/health/ping", include_in_schema=False)
async def health_check():
    return {"status": "ok", "service": "user"}
