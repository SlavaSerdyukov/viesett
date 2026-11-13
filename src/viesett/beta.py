"""Single-worker, fail-closed private-beta application factory."""

from fastapi import FastAPI

from viesett.api.app import create_app
from viesett.core.config import Settings


def create_beta_app() -> FastAPI:
    return create_app(Settings(private_beta=True))
