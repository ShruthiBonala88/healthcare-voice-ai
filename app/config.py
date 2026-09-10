"""
Centralized application settings.
Loaded from environment variables / .env via pydantic-settings.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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
