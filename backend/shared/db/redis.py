"""Redis async connection pool."""

from typing import Optional

import redis.asyncio as aioredis

from ..config import get_settings

_pool: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = aioredis.from_url(str(settings.redis_url), decode_responses=True, encoding="utf-8")
    return _pool


async def close_redis() -> None:
    global _pool
    if _pool:
        await _pool.aclose()
        _pool = None
