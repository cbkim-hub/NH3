from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class ApiResponse(BaseModel, Generic[T]):
    data: T | None
    meta: dict[str, Any] = {}
    error: ErrorResponse | None = None


def ok(data: T, meta: dict[str, Any] | None = None) -> ApiResponse[T]:
    return ApiResponse(data=data, meta=meta or {}, error=None)
