"""Risk Service — ML inference, score history, SHAP explanations."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ...shared.config import get_settings
from ...shared.security.hipaa_logger import HIPAAAuditMiddleware
from .routers.risk      import router as risk_router
from .routers.compute   import router as compute_router
from .routers.narrative import router as narrative_router

settings = get_settings()
logger   = logging.getLogger(__name__)

_model = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Try to pre-load the InferencePipeline at startup for warm latency.
    If torch / ml package / weights are missing, log and continue — compute.py
    will fall back to the heuristic scorer.
    """
    global _model
    try:
        import torch  # noqa: F401  (verify torch is available)
        from ml.inference.pipeline import InferencePipeline
        _model = InferencePipeline(
            model_path=settings.model_path,
            model_version=settings.model_version,
        )
        app.state.model = _model
        logger.info("Loaded NeuroGuard model from %s", settings.model_path)
    except Exception as e:
        logger.warning("Could not pre-load model (%s) — falling back to heuristic scorer", e)
        app.state.model = None
    yield
    _model = None


app = FastAPI(title="NeuroGuard Risk Service", version=settings.app_version, lifespan=lifespan)
app.add_middleware(HIPAAAuditMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(risk_router,      prefix="/api/v1/risk", tags=["risk"])
app.include_router(compute_router,   prefix="/api/v1/risk", tags=["risk"])
app.include_router(narrative_router, prefix="/api/v1/risk", tags=["risk"])


@app.get("/api/v1/health/ping", include_in_schema=False)
async def health_check():
    return {"status": "ok", "service": "risk"}
