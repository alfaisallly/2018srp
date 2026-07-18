import json
from typing import Any

import redis.asyncio as aioredis

from app.config import get_settings

settings = get_settings()
_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    redis = await get_redis()
    await redis.set(key, json.dumps(value, default=str), ex=ttl)


async def cache_get(key: str) -> Any | None:
    redis = await get_redis()
    data = await redis.get(key)
    if data:
        return json.loads(data)
    return None


async def publish_alert_event(alert_id: int, payload: dict) -> None:
    redis = await get_redis()
    await redis.publish("dcms:alerts", json.dumps({"alert_id": alert_id, **payload}, default=str))
