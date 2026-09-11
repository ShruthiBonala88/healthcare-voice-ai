<<<<<<< HEAD
"""
Centralized application settings.
Loaded from environment variables / .env via pydantic-settings.
"""
from functools import lru_cache
=======
from functools import lru_cache

>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
<<<<<<< HEAD
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000
    base_url: str = "http://localhost:8000"

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    twilio_validate_signature: bool = True

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_chat_model: str = "anthropic/claude-sonnet-4.5"
    openrouter_embedding_model: str = "openai/text-embedding-3-small"

    # STT
    stt_provider: str = "deepgram"
    deepgram_api_key: str = ""

    # TTS
    tts_provider: str = "elevenlabs"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_db_url: str = ""

    # Redis
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""

    # Safety / ops
    human_handoff_phone_number: str = ""
    max_call_duration_seconds: int = 900
    rate_limit_per_phone_per_hour: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
=======

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
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
