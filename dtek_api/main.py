# Copyright 2026 AX1111YT
# SPDX-License-Identifier: Apache-2.0

from contextlib import asynccontextmanager
import hmac
import logging
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from .dtek_client import DtekClient
from .errors import DtekError
from .rate_limit import limiter
from .routes import router
from .service import ScheduleService
from .settings import Settings, settings


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def create_app(configuration: Settings = settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        client = DtekClient(configuration.upstream_timeout_seconds)
        app.state.schedule_service = ScheduleService(client, configuration)
        try:
            yield
        finally:
            await client.close()

    app = FastAPI(
        title="DTEK Schedule API",
        description="A lightweight API for DTEK blackout schedules.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if configuration.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if configuration.docs_enabled else None,
    )
    app.state.limiter = limiter
    limiter.enabled = configuration.rate_limit_enabled
    app.include_router(router)

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_error_handler(
        _request: Request,
        _exc: RateLimitExceeded,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded."},
        )

    @app.get("/healthz")
    @limiter.shared_limit(settings.rate_limit, scope="api")
    async def health(request: Request) -> dict[str, str]:
        return {"status": "ok"}

    @app.middleware("http")
    async def api_key_guard(request: Request, call_next):
        if request.url.path.startswith("/v1/") and configuration.api_key:
            supplied = request.headers.get("authorization", "")
            expected = f"Bearer {configuration.api_key}"
            if not hmac.compare_digest(supplied, expected):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "A valid bearer token is required."},
                    headers={"WWW-Authenticate": "Bearer"},
                )
        return await call_next(request)

    @app.exception_handler(DtekError)
    async def dtek_error_handler(_request: Request, exc: DtekError) -> JSONResponse:
        logging.getLogger(__name__).warning("DTEK request failed: %s", exc.code)
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": exc.code, "message": exc.public_message},
        )

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run(
        "dtek_api.main:app",
        host=settings.host,
        port=settings.port,
        workers=1,
        access_log=False,
    )
