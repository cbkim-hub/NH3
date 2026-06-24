from __future__ import annotations

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_current_token_payload, get_current_user, revoke_token_jti
from app.core.response import ApiResponse, ok
from app.models.iam import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, LoginResponse, LogoutRequest, RefreshTokenRequest, TokenPair, UserMe
from app.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/login",
    response_model=ApiResponse[LoginResponse],
    summary="JWT 로그인",
    description="이메일/비밀번호를 검증하고 accessToken, refreshToken, 현재 사용자 정보를 반환합니다.",
)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return ok(AuthService(db).login(payload.email, payload.password))


@router.post(
    "/refresh",
    response_model=ApiResponse[TokenPair],
    summary="Refresh Token 갱신",
    description="저장된 active refresh token을 검증하고 refresh token rotation을 수행합니다.",
)
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    return ok(AuthService(db).refresh(payload.refresh_token))


@router.post(
    "/logout",
    response_model=ApiResponse[dict[str, str]],
    summary="로그아웃",
    description="현재 access token jti를 revoke하고, 요청 body의 refreshToken이 있으면 해당 refresh token도 revoke합니다.",
)
def logout(
    payload: dict = Depends(get_current_token_payload),
    request: LogoutRequest | None = Body(default=None),
    db: Session = Depends(get_db),
):
    revoke_token_jti(payload.get("jti"))
    AuthService(db).logout(request.refresh_token if request else None)
    return ok({"message": "Logged out"})


@router.get(
    "/me",
    response_model=ApiResponse[UserMe],
    summary="현재 사용자 조회",
    description="Bearer access token 기반으로 현재 사용자와 역할 정보를 반환합니다.",
)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(AuthService(db).to_user_me(current_user))


@router.post(
    "/change-password",
    response_model=ApiResponse[dict[str, str]],
    status_code=status.HTTP_200_OK,
    summary="비밀번호 변경",
    description="현재 비밀번호를 검증한 뒤 비밀번호를 변경하고 사용자의 모든 refresh token을 revoke합니다.",
)
def change_password(
    request: ChangePasswordRequest,
    token_payload: dict = Depends(get_current_token_payload),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    AuthService(db).change_password(current_user, request.current_password, request.new_password)
    revoke_token_jti(token_payload.get("jti"))
    return ok({"message": "Password changed"})
