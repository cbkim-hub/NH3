from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.core.security import (
    TokenPayloadError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    token_expires_at,
    verify_password,
)
from app.models.iam import RefreshToken, User
from app.schemas.auth import LoginResponse, TokenPair, UserMe


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def authenticate(self, email: str, password: str) -> User:
        user = self.db.scalar(
            select(User)
            .options(selectinload(User.roles), selectinload(User.organization))
            .where(User.email == email, User.status == "active")
        )
        if user is None or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        return user

    def to_user_me(self, user: User) -> UserMe:
        return UserMe(
            id=user.id,
            email=user.email,
            name=user.name,
            organizationId=user.organization_id,
            roleCodes=[role.code for role in user.roles],
        )

    def issue_token_pair(self, user: User) -> TokenPair:
        claims = {"email": user.email, "roles": [role.code for role in user.roles]}
        return TokenPair(
            accessToken=create_access_token(subject=str(user.id), claims=claims),
            refreshToken=create_refresh_token(subject=str(user.id), claims=claims),
        )

    def persist_refresh_token(self, user: User, refresh_token: str) -> RefreshToken:
        payload = decode_token(refresh_token, expected_type=TokenType.REFRESH)
        token_record = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=token_expires_at(payload),
            created_by=user.id,
        )
        self.db.add(token_record)
        return token_record

    def login(self, email: str, password: str) -> LoginResponse:
        user = self.authenticate(email, password)
        tokens = self.issue_token_pair(user)
        self.persist_refresh_token(user, tokens.refresh_token)
        self.db.commit()
        return LoginResponse(accessToken=tokens.access_token, refreshToken=tokens.refresh_token, user=self.to_user_me(user))

    def load_active_refresh_token(self, refresh_token: str) -> tuple[RefreshToken, dict]:
        try:
            payload = decode_token(refresh_token, expected_type=TokenType.REFRESH)
        except TokenPayloadError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

        token_record = self.db.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_token(refresh_token),
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
        )
        if token_record is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is invalid, expired, or revoked")
        return token_record, payload

    def refresh(self, refresh_token: str) -> TokenPair:
        token_record, token_payload = self.load_active_refresh_token(refresh_token)
        try:
            user_uuid = UUID(str(token_payload.get("sub")))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user id in token") from exc

        user = self.db.scalar(
            select(User)
            .options(selectinload(User.roles), selectinload(User.organization))
            .where(User.id == user_uuid, User.status == "active")
        )
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

        new_tokens = self.issue_token_pair(user)
        token_record.revoked_at = datetime.now(timezone.utc)
        token_record.replaced_by_token_hash = hash_token(new_tokens.refresh_token)
        self.persist_refresh_token(user, new_tokens.refresh_token)
        self.db.commit()
        return new_tokens

    def logout(self, refresh_token: str | None = None) -> None:
        if refresh_token:
            token_record = self.db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token)))
            if token_record and token_record.revoked_at is None:
                token_record.revoked_at = datetime.now(timezone.utc)
                self.db.commit()

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is invalid")
        user.password_hash = hash_password(new_password)
        self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        self.db.commit()
