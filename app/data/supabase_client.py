"""
Supabase client.

This client is used only by the backend.
The service role key must never be exposed
to frontend applications.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_supabase() -> Client:
    settings = get_settings()

    if not settings.supabase_url:
        raise RuntimeError(
            "SUPABASE_URL is not configured."
        )

    if not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is not configured."
        )

    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )