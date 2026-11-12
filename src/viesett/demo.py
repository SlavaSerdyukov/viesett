"""Explicit opt-in local demo entrypoint; all outbound providers are synthetic."""

from fastapi import FastAPI

from viesett.api.app import create_app
from viesett.core.config import PROJECT_ROOT, Settings


def create_demo_app() -> FastAPI:
    settings = Settings()
    if not settings.demo_mode or settings.environment == "production":
        raise RuntimeError("Enable VIESETT_DEMO_MODE only for a local development/test instance")
    if settings.storage_root == PROJECT_ROOT / ".local" / "objects":
        settings = settings.model_copy(
            update={"storage_root": PROJECT_ROOT / ".local" / "demo-objects"}
        )
    return create_app(settings)
