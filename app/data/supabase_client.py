"""
Supabase client singleton (service role — server-side only, never expose
this key to the client/browser).
"""
from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_supabase() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not configured. "
            "Copy .env.example to .env and fill in your Supabase project details."
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
