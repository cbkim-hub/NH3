from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import TokenPayloadError, TokenType, decode_token
from app.models.iam import User

bearer_scheme = HTTPBearer(auto_error=False)
revoked_token_jtis: set[str] = set()


class RoleCode(StrEnum):
    SUPER_ADMIN = "SuperAdmin"
    ADMIN = "Admin"
    MANAGER = "Manager"
    OPERATOR = "Operator"
    FIELD_WORKER = "FieldWorker"


ROLE_HIERARCHY: dict[RoleCode, int] = {
    RoleCode.SUPER_ADMIN: 100,
    RoleCode.ADMIN: 80,
    RoleCode.MANAGER: 60,
    RoleCode.OPERATOR: 40,
    RoleCode.FIELD_WORKER: 20,
}


def revoke_token_jti(jti: str | None) -> None:
    if jti:
        revoked_token_jtis.add(jti)


def is_token_revoked(jti: str | None) -> bool:
    return bool(jti and jti in revoked_token_jtis)


def _credentials_error(message: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise _credentials_error("Authentication required")
    try:
        payload = decode_token(credentials.credentials, expected_type=TokenType.ACCESS)
    except TokenPayloadError as exc:
        raise _credentials_error(str(exc)) from exc
    if is_token_revoked(payload.get("jti")):
        raise _credentials_error("Token has been revoked")
    return payload


def get_current_user(
    payload: dict = Depends(get_current_token_payload),
    db: Session = Depends(get_db),
) -> User:
    user_id = payload.get("sub")
    try:
        user_uuid = UUID(str(user_id))
    except ValueError as exc:
        raise _credentials_error("Invalid user id in token") from exc

    user = db.scalar(
        select(User)
        .options(selectinload(User.roles), selectinload(User.organization))
        .where(User.id == user_uuid, User.status == "active")
    )
    if user is None:
        raise _credentials_error("User not found or inactive")
    return user


def user_role_codes(user: User) -> set[str]:
    return {role.code for role in user.roles}


def require_roles(*allowed_roles: RoleCode):
    allowed = {role.value for role in allowed_roles}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if RoleCode.SUPER_ADMIN.value in user_role_codes(current_user):
            return current_user
        if not user_role_codes(current_user).intersection(allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {', '.join(sorted(allowed))}",
            )
        return current_user

    return dependency


def require_min_role(min_role: RoleCode):
    minimum_level = ROLE_HIERARCHY[min_role]

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        levels: list[int] = []
        for role in current_user.roles:
            try:
                levels.append(ROLE_HIERARCHY[RoleCode(role.code)])
            except ValueError:
                continue
        max_level = max(levels, default=0)
        if max_level < minimum_level:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Required minimum role: {min_role.value}")
        return current_user

    return dependency
