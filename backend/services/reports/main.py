"""Reports Service — PDF generation via ReportLab, S3 upload, signed URL."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ...shared.config import get_settings
from ...shared.security.hipaa_logger import HIPAAAuditMiddleware
from .routers.reports import router as reports_router

settings = get_settings()

app = FastAPI(title="NeuroGuard Reports Service", version=settings.app_version)
app.add_middleware(HIPAAAuditMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(reports_router, prefix="/api/v1/reports", tags=["reports"])


@app.get("/api/v1/health/ping", include_in_schema=False)
async def health_check():
    return {"status": "ok", "service": "reports"}
