"""
Upstash Redis client singleton, used for:
  - rate limiting (per-phone-number call attempts)
  - short-lived session/turn state during an active call
  - distributed locks (e.g. prevent double-booking the same slot)
"""
from functools import lru_cache

from upstash_redis import Redis

from app.config import get_settings


@lru_cache
def get_redis() -> Redis:
    settings = get_settings()
    if not settings.upstash_redis_rest_url or not settings.upstash_redis_rest_token:
        raise RuntimeError(
            "UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN are not configured."
        )
    return Redis(
        url=settings.upstash_redis_rest_url,
        token=settings.upstash_redis_rest_token,
    )


def rate_limit_key(phone_number: str) -> str:
    return f"ratelimit:call:{phone_number}"


def session_key(call_sid: str) -> str:
    return f"session:{call_sid}"


def lock_key(resource: str) -> str:
    return f"lock:{resource}"
