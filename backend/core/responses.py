"""Standard response envelope used across all endpoints.

Every authenticated endpoint returns ``{ ...payload, success, message }`` per
the TSD response shapes. Generic base lets each domain add typed fields.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel):
    success: bool = True
    message: str | None = None


class DataResponse(ApiResponse, Generic[T]):
    data: T | None = None
