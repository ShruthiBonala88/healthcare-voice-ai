"""
Centralized application settings for Voxevia.

Configuration is loaded from environment variables and .env
using pydantic-settings.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    # ============================================================
    # APPLICATION
    # ============================================================

    app_env: str = "development"
    log_level: str = "INFO"

    host: str = "127.0.0.1"
    port: int = 8000

    base_url: str = "http://127.0.0.1:8000"

    # ============================================================
    # TWILIO
    # ============================================================

    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_phone_number: str | None = None

    twilio_validate_signature: bool = False

    # ============================================================
    # OPENROUTER
    # ============================================================

    openrouter_api_key: str | None = None

    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    openrouter_chat_model: str | None = None

    openrouter_embedding_model: str | None = None

    # ============================================================
    # SPEECH-TO-TEXT
    # ============================================================

    stt_provider: str = "whisper"

    whisper_model: str = "small"

    whisper_device: str = "cpu"

    whisper_compute_type: str = "int8"

    # ============================================================
    # TEXT-TO-SPEECH
    # ============================================================

    tts_provider: str = "elevenlabs"

    elevenlabs_api_key: str | None = None

    elevenlabs_voice_id: str | None = None

    # ============================================================
    # SUPABASE
    # ============================================================

    supabase_url: str | None = None

    supabase_service_role_key: str | None = None

    supabase_db_url: str | None = None

    # ============================================================
    # UPSTASH REDIS
    # ============================================================

    upstash_redis_rest_url: str | None = None

    upstash_redis_rest_token: str | None = None

    # ============================================================
    # HUMAN HANDOFF
    # ============================================================

    human_handoff_phone_number: str | None = None

    # ============================================================
    # CALL SETTINGS
    # ============================================================

    max_call_duration_seconds: int = 1800

    rate_limit_per_phone_per_hour: int = 20

    # ============================================================
    # PYDANTIC SETTINGS CONFIGURATION
    # ============================================================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
    )


# ================================================================
# SETTINGS SINGLETON
# ================================================================

@lru_cache
def get_settings() -> Settings:
    return Settings()