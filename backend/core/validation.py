"""Shared router-level input validators.

These are called at the top of each handler to reject clearly invalid inputs
before any service or DB work begins.
"""
from __future__ import annotations

import uuid

from backend.database.exceptions import ValidationError


def validate_uuid(value: str, field: str) -> None:
    """Raise ValidationError if *value* is not a valid UUID string."""
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ValidationError(f"'{field}' must be a valid UUID, got: {value!r}.")


def validate_nonempty(value: str | None, field: str) -> None:
    """Raise ValidationError if *value* is None or blank."""
    if not (value and value.strip()):
        raise ValidationError(f"'{field}' must not be empty.")


def validate_one_of(value: str, choices: tuple[str, ...], field: str) -> None:
    """Raise ValidationError if *value* is not one of *choices*."""
    if value not in choices:
        raise ValidationError(
            f"'{field}' must be one of {list(choices)}, got: {value!r}."
        )
