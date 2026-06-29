"""Custom domain exceptions.

Raised by services and mapped to HTTP responses by a single exception handler
registered in ``main.py``. Routers stay thin and never build error payloads.
"""

from typing import Any


class DomainError(Exception):
    """Base class for all domain errors.

    Attributes:
        status_code: HTTP status to return.
        message: Human-readable message surfaced to the client.
        detail: Optional structured detail.
    """

    status_code: int = 400

    def __init__(self, message: str, *, detail: Any = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(DomainError):
    status_code = 404


class ValidationError(DomainError):
    status_code = 400


class DuplicateError(DomainError):
    status_code = 409


class UnauthorizedError(DomainError):
    status_code = 401


class ForbiddenError(DomainError):
    status_code = 403


class UnsupportedMediaTypeError(DomainError):
    status_code = 415


class UpstreamError(DomainError):
    """MainSubSys / storage upstream failure."""

    status_code = 502
