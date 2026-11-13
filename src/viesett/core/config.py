from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, SecretStr, model_validator
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
    web_origins: list[str] = []
    allow_development_web_sessions: bool = False
    demo_mode: bool = False
    preview_rate_limit_per_minute: int = Field(default=5, ge=1, le=30)
    browser_sessions_enabled: bool = False
    browser_cookie_secure: bool = True
    browser_session_hours: int = Field(default=8, ge=1, le=24)
    private_beta: bool = False
    application_workers: int = Field(
        default=1,
        ge=1,
        validation_alias=AliasChoices(
            "VIESETT_APPLICATION_WORKERS", "WEB_CONCURRENCY", "application_workers"
        ),
    )
    token_lifetime_hours: int = Field(default=24, ge=1, le=168)
    grar_api_key: SecretStr | None = Field(
        default=None,
        repr=False,
        exclude=True,
        validation_alias=AliasChoices("VIESETT_GRAR_API_KEY", "GRAR_API_KEY", "grar_api_key"),
    )
    official_sources_enabled: bool = True
    official_sources_reviewed: bool = False
    source_connect_timeout: float = Field(default=2, gt=0, le=10)
    source_read_timeout: float = Field(default=4, gt=0, le=15)
    source_write_timeout: float = Field(default=2, gt=0, le=10)
    source_pool_timeout: float = Field(default=1, gt=0, le=10)
    source_operation_timeout: float = Field(default=20, gt=0, le=25)
    source_attempts: int = Field(default=2, ge=1, le=3)
    source_min_interval: float = Field(default=0.35, ge=0, le=2)
    source_retry_base: float = Field(default=0.3, ge=0, le=1)
    run_live_source_tests: bool = False
    pdf_max_pages: int = Field(default=150, ge=1, le=500)
    pdf_max_characters: int = Field(default=500_000, ge=100, le=2_000_000)
    pdf_max_stream_bytes: int = Field(default=4 * 1024 * 1024, ge=1024, le=16 * 1024 * 1024)
    pdf_timeout_seconds: float = Field(default=8, gt=0, le=15)

    @model_validator(mode="after")
    def validate_safety(self) -> "Settings":
        if not self.database_url.get_secret_value().startswith("postgresql+asyncpg://"):
            raise ValueError("PostgreSQL with asyncpg is required")
        if self.max_request_bytes < self.max_upload_bytes:
            raise ValueError("Request limit must cover the upload limit")
        if any(
            origin == "*"
            or not origin.startswith(("http://", "https://"))
            or origin.rstrip("/") != origin
            for origin in self.web_origins
        ):
            raise ValueError("Explicit web origins without a trailing slash are required")
        for origin in self.web_origins:
            parsed = urlsplit(origin)
            if (
                not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
                or "*" in origin
            ):
                raise ValueError("A web origin must contain only scheme, host and optional port")
        if self.browser_sessions_enabled and not self.web_origins:
            raise ValueError("Browser sessions require explicit web origins")
        if self.private_beta and (
            self.environment != "production"
            or not self.browser_sessions_enabled
            or not self.browser_cookie_secure
            or self.demo_mode
            or self.allow_development_web_sessions
            or self.allow_development_safety
            or self.application_workers != 1
            or not self.allowed_hosts
            or not self.storage_root.is_absolute()
            or self.storage_root == PROJECT_ROOT
            or self.storage_root.is_relative_to(PROJECT_ROOT / "web")
            or bool(set(self.allowed_hosts) & {"localhost", "127.0.0.1", "testserver", "*"})
            or self.storage_root == PROJECT_ROOT / ".local" / "objects"
            or (self.official_sources_enabled and not self.official_sources_reviewed)
        ):
            raise ValueError("Private beta requires reviewed production settings and one worker")
        if self.environment == "production":
            if self.browser_sessions_enabled and (
                not self.browser_cookie_secure
                or any(not o.startswith("https://") for o in self.web_origins)
            ):
                raise ValueError(
                    "Production browser sessions require HTTPS origins and Secure cookies"
                )
            if self.allow_development_web_sessions or self.demo_mode:
                raise ValueError(
                    "Development web sessions and demo mode are forbidden in production"
                )
            if self.allow_development_safety:
                raise ValueError("Development safety adapters are forbidden in production")
            if "*" in self.allowed_hosts:
                raise ValueError("Explicit production hosts are required")
            if "development-only" in self.database_url.get_secret_value():
                raise ValueError("Production database credentials must be configured")
        return self
