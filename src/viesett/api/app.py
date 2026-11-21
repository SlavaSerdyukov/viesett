from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from viesett.ai.boundary import validate_production_processors
from viesett.api.browser_routes import router as browser_router
from viesett.api.coownership_routes import router as coownership_router
from viesett.api.dependencies import Runtime
from viesett.api.intelligence_routes import router as intelligence_router
from viesett.api.product_routes import router as product_router
from viesett.api.property_routes import router as property_router
from viesett.api.routes import router
from viesett.core.config import Settings
from viesett.core.security import MemoryRateLimiter, RateLimiter, SecurityMiddleware
from viesett.db.product_models import DemoWorkspace
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
    if config.demo_mode and source_transport is None:
        from viesett.demo_data import DemoOfficialService

        source_transport = httpx.MockTransport(DemoOfficialService(match_queries=True).handler)
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
        beta_connection: AsyncConnection | None = None
        beta_lock_acquired = False
        try:
            if config.environment == "production":
                if not safety.scanner.production_ready or not safety.gate.production_ready:
                    raise RuntimeError("Reviewed production document safety adapters are required")
                async with context.sessions() as db:
                    if await db.scalar(select(DemoWorkspace.workspace_id).limit(1)) is not None:
                        raise RuntimeError("Use a separate database for demo workspaces")
                    await validate_production_processors(db)
            if config.private_beta:
                # A dedicated connection holds a database-wide session lock:
                # a second worker/instance sharing this beta DB fails closed.
                beta_connection = await engine.connect()
                beta_lock_acquired = bool(
                    await beta_connection.scalar(
                        text("SELECT pg_try_advisory_lock(24287472861041748)")
                    )
                )
                if not beta_lock_acquired:
                    raise RuntimeError("Private beta permits one application worker per database")
            yield
        finally:
            if beta_connection is not None:
                if beta_lock_acquired:
                    await beta_connection.execute(
                        text("SELECT pg_advisory_unlock(24287472861041748)")
                    )
                await beta_connection.close()
            await context.sources.aclose()
            await engine.dispose()

    production = config.environment == "production"
    app = FastAPI(
        title="Viesett",
        version="0.6.0",
        debug=False,
        lifespan=lifespan,
        docs_url=None if production else "/docs",
        redoc_url=None,
        openapi_url=None if production else "/openapi.json",
    )
    app.state.preview_limiter = MemoryRateLimiter(config.preview_rate_limit_per_minute, 1000)
    app.state.session_limiter = MemoryRateLimiter(5, 100)
    app.state.browser_limiter = MemoryRateLimiter(10, 1000)
    app.state.runtime = context
    app.state.engine = engine
    app.include_router(product_router)
    app.include_router(browser_router)
    app.include_router(router)
    app.include_router(property_router)
    app.include_router(intelligence_router)
    app.include_router(coownership_router)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.allowed_hosts)
    if config.web_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.web_origins,
            allow_credentials=config.browser_sessions_enabled,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-Filename", "X-CSRF-Token"],
        )
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
                await db.execute(text("SELECT id FROM co_ownership_evaluations LIMIT 1"))
                await db.execute(text("SELECT workspace_id FROM demo_workspaces LIMIT 1"))
                if config.browser_sessions_enabled:
                    await db.execute(text("SELECT id FROM browser_sessions LIMIT 1"))
                if production:
                    await validate_production_processors(db)
        except Exception:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ok"})

    return app
