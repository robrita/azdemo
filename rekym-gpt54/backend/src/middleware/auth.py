"""Simple auth dependency for the starter template."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import Request

from src.exceptions import UnauthorizedError


class AuthUser(BaseModel):
    user_id: str
    role: str
    tenant_id: str


async def get_current_user(request: Request) -> AuthUser:
    settings = request.app.state.settings
    if settings.auth_mode == "disabled":
        return AuthUser(user_id="dev-user", role=settings.dev_persona, tenant_id="tenant-demo")

    user_id = request.headers.get("X-User-Id", "").strip()
    role = request.headers.get("X-User-Role", "").strip()
    tenant_id = request.headers.get("X-Tenant-Id", "").strip()

    if not user_id or not role or not tenant_id:
        raise UnauthorizedError(
            "Missing X-User-Id, X-User-Role, or X-Tenant-Id headers for header auth mode",
        )

    return AuthUser(user_id=user_id, role=role, tenant_id=tenant_id)