"""
Redis client for Voxevia.

Used for:
- Temporary call/session state
- Rate limiting
- Distributed locks
- Short-lived data
"""

import json
from typing import Any

from upstash_redis import Redis

from app.config import get_settings


# ---------------------------------------------------------
# Redis client
# ---------------------------------------------------------

_redis: Redis | None = None


def get_redis() -> Redis:
    """
    Return the shared Upstash Redis client.

    The client is created only once and reused for the
    lifetime of the application process.
    """

    global _redis

    if _redis is None:
        settings = get_settings()

        if not settings.upstash_redis_rest_url:
            raise RuntimeError(
                "UPSTASH_REDIS_REST_URL is not configured."
            )

        if not settings.upstash_redis_rest_token:
            raise RuntimeError(
                "UPSTASH_REDIS_REST_TOKEN is not configured."
            )

        _redis = Redis(
            url=settings.upstash_redis_rest_url,
            token=settings.upstash_redis_rest_token,
        )

    return _redis


# ---------------------------------------------------------
# Redis connection test
# ---------------------------------------------------------

def redis_ping() -> bool:
    """
    Check whether Redis is reachable.
    """

    redis = get_redis()

    result = redis.ping()

    return result == "PONG"


# ---------------------------------------------------------
# Session management
# ---------------------------------------------------------

def set_session(
    session_id: str,
    data: dict[str, Any],
    ttl_seconds: int = 1800,
) -> bool:
    """
    Store temporary call/session data in Redis.

    Example Redis key:

        session:abc123
    """

    if not isinstance(session_id, str):
        raise ValueError("session_id must be a string.")

    if not session_id.strip():
        raise ValueError("session_id cannot be empty.")

    if ttl_seconds <= 0:
        raise ValueError(
            "ttl_seconds must be greater than zero."
        )

    if not isinstance(data, dict):
        raise ValueError(
            "Session data must be a dictionary."
        )

    redis = get_redis()

    key = f"session:{session_id}"

    serialized_data = json.dumps(
        data,
        default=str,
    )

    redis.set(
        key,
        serialized_data,
        ex=ttl_seconds,
    )

    return True


def get_session(
    session_id: str,
) -> dict[str, Any] | None:
    """
    Retrieve temporary session data from Redis.

    Returns:
        Dictionary when the session exists.
        None when the session does not exist.
    """

    if not isinstance(session_id, str):
        raise ValueError("session_id must be a string.")

    if not session_id.strip():
        raise ValueError("session_id cannot be empty.")

    redis = get_redis()

    key = f"session:{session_id}"

    data = redis.get(key)

    if data is None:
        return None

    if isinstance(data, bytes):
        data = data.decode("utf-8")

    try:
        return json.loads(data)

    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Invalid session data stored in Redis."
        ) from exc


def update_session(
    session_id: str,
    updates: dict[str, Any],
    ttl_seconds: int = 1800,
) -> dict[str, Any]:
    """
    Update an existing Redis session.

    Existing session values are preserved and the
    supplied values are merged into the session.
    """

    if not isinstance(session_id, str):
        raise ValueError("session_id must be a string.")

    if not session_id.strip():
        raise ValueError("session_id cannot be empty.")

    if not isinstance(updates, dict):
        raise ValueError(
            "Session updates must be a dictionary."
        )

    current_session = get_session(session_id)

    if current_session is None:
        raise KeyError(
            f"Session '{session_id}' does not exist."
        )

    current_session.update(updates)

    set_session(
        session_id=session_id,
        data=current_session,
        ttl_seconds=ttl_seconds,
    )

    return current_session


def delete_session(
    session_id: str,
) -> bool:
    """
    Delete a temporary session from Redis.
    """

    if not isinstance(session_id, str):
        raise ValueError("session_id must be a string.")

    if not session_id.strip():
        raise ValueError("session_id cannot be empty.")

    redis = get_redis()

    key = f"session:{session_id}"

    result = redis.delete(key)

    return result > 0


def refresh_session(
    session_id: str,
    ttl_seconds: int = 1800,
) -> bool:
    """
    Refresh the TTL of an existing session.
    """

    if not isinstance(session_id, str):
        raise ValueError("session_id must be a string.")

    if not session_id.strip():
        raise ValueError("session_id cannot be empty.")

    if ttl_seconds <= 0:
        raise ValueError(
            "ttl_seconds must be greater than zero."
        )

    current_session = get_session(session_id)

    if current_session is None:
        return False

    set_session(
        session_id=session_id,
        data=current_session,
        ttl_seconds=ttl_seconds,
    )

    return True


# ---------------------------------------------------------
# Distributed lock key
# ---------------------------------------------------------

def lock_key(resource: str) -> str:
    """
    Build a Redis key for a distributed lock.

    Example:

        lock_key("slot:123")

    Returns:

        lock:slot:123
    """

    if not isinstance(resource, str):
        raise ValueError("resource must be a string.")

    resource = resource.strip()

    if not resource:
        raise ValueError("resource cannot be empty.")

    return f"lock:{resource}"