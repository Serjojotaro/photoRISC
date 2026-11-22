from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app import db
from app.api import register_exception_handlers, router
from app.build_info import BuildInfo, load_build_info
from app.config import Settings


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    build_info: BuildInfo | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    resolved_build = build_info or load_build_info(resolved_settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        resolved_settings.ensure_directories()
        db.init_db(resolved_settings)
        logger.info("PhotoRISC %s started", resolved_build.display)
        yield

    application = FastAPI(
        title="PhotoRISC API",
        version=resolved_build.version,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.build_info = resolved_build

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID") or str(
            uuid.uuid4()
        )
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Request failed: request_id=%s",
                request.state.request_id,
            )
            raise
        response.headers["X-Request-ID"] = request.state.request_id
        if request.url.path.startswith("/api/v1"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    application.include_router(router)
    register_exception_handlers(application)
    return application


app = create_app()
