from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VIESETT_", extra="ignore", hide_input_in_errors=True
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://viesett:development-only@localhost:5432/viesett"
    )
    storage_root: Path = PROJECT_ROOT / ".local" / "objects"
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=50 * 1024 * 1024)
    max_request_bytes: int = Field(default=11 * 1024 * 1024, ge=1, le=51 * 1024 * 1024)
    request_timeout_seconds: float = Field(default=30, gt=0, le=120)
    statement_timeout_ms: int = Field(default=5000, ge=100, le=60000)
    rate_limit_per_minute: int = Field(default=120, ge=1)
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    allow_development_safety: bool = False
    archived_retention_days: int | None = Field(default=None, ge=1)
    token_lifetime_hours: int = Field(default=24, ge=1, le=168)

    @model_validator(mode="after")
    def validate_safety(self) -> "Settings":
        if not self.database_url.get_secret_value().startswith("postgresql+asyncpg://"):
            raise ValueError("PostgreSQL with asyncpg is required")
        if self.max_request_bytes < self.max_upload_bytes:
            raise ValueError("Request limit must cover the upload limit")
        if self.environment == "production":
            if self.allow_development_safety:
                raise ValueError("Development safety adapters are forbidden in production")
            if "*" in self.allowed_hosts:
                raise ValueError("Explicit production hosts are required")
            if "development-only" in self.database_url.get_secret_value():
                raise ValueError("Production database credentials must be configured")
        return self
