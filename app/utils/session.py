"""
Small helpers for rate limiting via Redis, used before accepting a call
(or in routes_calls.py) to cap how many attempts a phone number can make
per hour.
"""
from app.config import get_settings
from app.data.redis_client import get_redis, rate_limit_key


def check_and_increment_rate_limit(phone_number: str) -> bool:
    """Returns True if the caller is within their allowed rate, False if blocked."""
    settings = get_settings()
    redis = get_redis()
    key = rate_limit_key(phone_number)

    count = redis.incr(key)
    if count == 1:
        redis.expire(key, 3600)

    return count <= settings.rate_limit_per_phone_per_hour
