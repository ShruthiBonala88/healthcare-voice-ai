"""
<<<<<<< HEAD
Supabase client singleton (service role — server-side only, never expose
this key to the client/browser).
"""
=======
Supabase client.

This client is used only by the backend.
The service role key must never be exposed
to frontend applications.
"""

>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_supabase() -> Client:
    settings = get_settings()
<<<<<<< HEAD
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not configured. "
            "Copy .env.example to .env and fill in your Supabase project details."
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
=======

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
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
