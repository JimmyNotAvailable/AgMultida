from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from backend.core.config import get_settings
from backend.core.errors import AgTechError, ErrorCode
from backend.core.rate_limit import check_rate_limit
from backend.core.schemas import LoginRequest, MeResponse, RefreshRequest, TokenResponse
from backend.core.security import create_access_token, create_refresh_token, decode_refresh_token, require_role, verify_admin_credentials

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def build_token_response(username: str, role: str) -> TokenResponse:
    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(username, role),
        refresh_token=create_refresh_token(username, role),
        expires_in=settings.JWT_EXPIRY_MINUTES * 60,
        role=role,
        username=username,
    )


async def auth_rate_limit(request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    await check_rate_limit("auth", client_host)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
async def login(request: LoginRequest):
    if not verify_admin_credentials(request.username, request.password):
        raise AgTechError(
            error_code=ErrorCode.AUTH_INVALID_TOKEN,
            message="Invalid credentials",
            status_code=401,
        )
    return build_token_response(request.username, "admin")


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
async def refresh(request: RefreshRequest):
    payload = decode_refresh_token(request.refresh_token)
    return build_token_response(payload["sub"], payload.get("role", "admin"))


@router.get("/me", response_model=MeResponse, dependencies=[Depends(require_role("viewer", "operator", "admin"))])
async def me(request: Request):
    payload = request.state.auth_context
    return MeResponse(username=payload["sub"], role=payload["role"])
