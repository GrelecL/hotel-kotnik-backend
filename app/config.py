from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://hotel:hotel@db:5432/hotel_kotnik"
    redis_url: str = "redis://redis:6379/0"
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:3b"

    email_poll_interval: int = 45  # seconds
    email_inbox_folder: str = "INBOX"

    # Tailscale bind address - API binds only here
    bind_host: str = "0.0.0.0"
    bind_port: int = 8000

    fernet_key: str = ""  # base64-encoded 32-byte key for IMAP password encryption


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
