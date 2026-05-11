"""API Gateway wiring: middleware, lifespan, and router mounting."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from backend.api_gateway.dependencies import ADMIN_READ_DEPENDENCIES, ADMIN_WRITE_DEPENDENCIES
from backend.api_gateway.lifespan import initialize_application_state, shutdown_application_services, wire_application_services
from backend.core.config import get_settings
from backend.core.errors import AgTechError, mask_internal_exception
from backend.features.alerts.router import router as alerts_router
from backend.features.auth.router import router as auth_router
from backend.features.commands.router import router as commands_router
from backend.features.health.router import router as health_router
from backend.features.imagery.router import router as imagery_router
from backend.features.prediction.router import router as prediction_router
from backend.features.recommendation.router import router as recommendation_router
from backend.features.websocket.router import router as websocket_router
from backend.features.zones.router import router as zones_router

logger = logging.getLogger("agtech.gateway")


@asynccontextmanager
async def lifespan(application: FastAPI):
    await wire_application_services(application)
    yield
    await shutdown_application_services(application)


app = FastAPI(title="AgMultida API Gateway", version="1.0.0", lifespan=lifespan)
initialize_application_state(app)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", settings.INTERNAL_API_KEY_HEADER],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.TRUSTED_HOSTS))


@app.exception_handler(AgTechError)
async def agtech_error_handler(request: Request, exc: AgTechError):
    return JSONResponse(status_code=exc.status_code, content=exc.to_response().model_dump(mode="json"))


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    resp = mask_internal_exception(exc)
    return JSONResponse(status_code=500, content=resp.model_dump(mode="json"))


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if get_settings().ENABLE_HSTS:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID") or str(uuid4())
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    return response


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(zones_router)
app.include_router(prediction_router, dependencies=ADMIN_WRITE_DEPENDENCIES)
app.include_router(recommendation_router, dependencies=ADMIN_WRITE_DEPENDENCIES)
app.include_router(commands_router, dependencies=ADMIN_WRITE_DEPENDENCIES)
app.include_router(imagery_router)
app.include_router(alerts_router, dependencies=ADMIN_WRITE_DEPENDENCIES)
app.include_router(websocket_router)
