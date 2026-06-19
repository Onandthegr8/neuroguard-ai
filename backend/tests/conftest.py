"""Shared pytest fixtures for NeuroGuard backend tests."""
import os
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── Set test environment BEFORE importing app modules ────────────────────────
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test_user:test_password@localhost:5432/neuroguard_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("AUTH0_DOMAIN", "test.auth0.com")
os.environ.setdefault("AUTH0_AUDIENCE", "https://api.test.neuroguard.health")
os.environ.setdefault("FIELD_ENCRYPTION_KEY", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXRlc3Rpbmch")
os.environ.setdefault("JWT_SECRET", "test-secret-for-ci-only")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("S3_BUCKET_REPORTS", "test-reports")
os.environ.setdefault("S3_BUCKET_MODELS", "test-models")

from backend.shared.models.base import Base  # noqa: E402
from backend.shared.db.session import get_db  # noqa: E402


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create a test database engine (session-scoped)."""
    url = os.environ["DATABASE_URL"]
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional test session that rolls back after each test."""
    async_session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def auth_client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client for the auth service."""
    from backend.services.auth.main import app

    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def health_client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client for the health service."""
    from backend.services.health.main import app

    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_user_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def sample_keystroke_payload(sample_user_id):
    """Minimal valid keystroke ingest payload."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    return {
        "device_id": str(uuid.uuid4()),
        "session_start": (now - timedelta(minutes=5)).isoformat(),
        "session_end": now.isoformat(),
        "key_press_duration_ms": [85.2, 92.1, 78.4, 110.3, 95.6] * 10,
        "inter_key_interval_ms": [120.5, 135.2, 98.7, 145.1, 108.9] * 10,
        "typing_speed_wpm": 52.3,
        "correction_frequency": 0.08,
        "typing_entropy": 3.21,
        "autocorrect_rate": 0.12,
        "diurnal_hour": 14,
        "app_context": "messaging",
    }
