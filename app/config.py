"""Centralized application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
    )

    app_env: str = "development"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000
    base_url: str = "http://localhost:8000"

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    twilio_validate_signature: bool = True

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_chat_model: str = "anthropic/claude-sonnet-4.5"
    openrouter_embedding_model: str = "openai/text-embedding-3-small"

    stt_provider: str = "deepgram"
    deepgram_api_key: str = ""
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    tts_provider: str = "elevenlabs"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_db_url: str = ""

    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""
    human_handoff_phone_number: str = ""
    max_call_duration_seconds: int = 900
    rate_limit_per_phone_per_hour: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
