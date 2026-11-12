from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from viesett.ai.boundary import validate_production_processors
from viesett.api.dependencies import Runtime
from viesett.api.intelligence_routes import router as intelligence_router
from viesett.api.property_routes import router as property_router
from viesett.api.routes import router
from viesett.core.config import Settings
from viesett.core.security import MemoryRateLimiter, RateLimiter, SecurityMiddleware
from viesett.db.session import create_engine, session_factory
from viesett.document_safety.pipeline import (
    ConservativeSensitiveGate,
    DevelopmentScanner,
    SafetyPipeline,
    UnavailableScanner,
)
from viesett.integrations.sources import PublicSources
from viesett.storage.private import LocalPrivateStorage, PrivateObjectStorage


def create_app(
    settings: Settings | None = None,
    *,
    storage: PrivateObjectStorage | None = None,
    pipeline: SafetyPipeline | None = None,
    limiter: RateLimiter | None = None,
    source_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    config = settings or Settings()
    engine = create_engine(config)
    safety = pipeline or SafetyPipeline(
        DevelopmentScanner() if config.allow_development_safety else UnavailableScanner(),
        ConservativeSensitiveGate(),
    )
    limits = limiter or MemoryRateLimiter(config.rate_limit_per_minute)
    context = Runtime(
        config,
        engine,
        session_factory(engine),
        storage or LocalPrivateStorage(config.storage_root),
        safety,
        limits,
        PublicSources(config, source_transport),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            if config.environment == "production":
                if not safety.scanner.production_ready or not safety.gate.production_ready:
                    raise RuntimeError("Reviewed production document safety adapters are required")
                async with context.sessions() as db:
                    await validate_production_processors(db)
            yield
        finally:
            await context.sources.aclose()
            await engine.dispose()

    production = config.environment == "production"
    app = FastAPI(
        title="Viesett",
        version="0.3.0",
        debug=False,
        lifespan=lifespan,
        docs_url=None if production else "/docs",
        redoc_url=None,
        openapi_url=None if production else "/openapi.json",
    )
    app.state.runtime = context
    app.state.engine = engine
    app.include_router(router)
    app.include_router(property_router)
    app.include_router(intelligence_router)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.allowed_hosts)
    app.add_middleware(SecurityMiddleware, settings=config, limiter=limits)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse({"detail": "Invalid request"}, status_code=422)

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready() -> JSONResponse:
        try:
            async with context.sessions() as db:
                # Checks schema presence as well as connectivity; never creates tables.
                await db.execute(text("SELECT id FROM policy_versions LIMIT 1"))
                await db.execute(text("SELECT id FROM property_resolutions LIMIT 1"))
                await db.execute(text("SELECT id FROM document_analyses LIMIT 1"))
                if production:
                    await validate_production_processors(db)
        except Exception:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ok"})

    return app
