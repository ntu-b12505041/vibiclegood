"""Runtime configuration. The frontend never receives these database settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")
    api_env: Literal["development", "test", "production"] = "development"
    postgres_host: str = "127.0.0.1"
    postgres_port: int = Field(default=55432, ge=1, le=65535)
    postgres_db: str = "vibicle_dev"
    postgres_user: str = "vibicle_migrator"
    postgres_password: SecretStr
    public_origin: str = "http://127.0.0.1:5173"
    rate_limit_secret: SecretStr | None = None
    private_image_root: Path = ENV_FILE.parent / "output" / "private"

    @property
    def database_url(self) -> URL:
        # URL.create handles password escaping without concatenating a URL.
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
