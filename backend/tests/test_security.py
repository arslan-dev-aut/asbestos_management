"""Unit tests for the review's security fixes (no DB / app required)."""

from __future__ import annotations

import pytest

from backend.config import Settings
from backend.core import storage
from backend.database.exceptions import UnsupportedMediaTypeError
from backend.domains.bulk.bulk_service import _formula_safe


# ── S2: production must forbid the unsigned-token dev bypass ──────────────────
def test_prod_guard_rejects_dev_fallback():
    # pydantic wraps the validator's ValueError in its own ValidationError.
    with pytest.raises(Exception):
        Settings(application_environment="production", auth_dev_fallback=True)


def test_prod_allows_dev_fallback_off():
    s = Settings(application_environment="production", auth_dev_fallback=False)
    assert s.is_production is True


# ── S5: CSV/spreadsheet formula injection neutralised ─────────────────────────
@pytest.mark.parametrize("dangerous", ["=cmd|'/c calc'!A1", "+1+1", "-2+3", "@SUM(A1)", "\tx"])
def test_formula_safe_prefixes_dangerous_cells(dangerous):
    out = _formula_safe(dangerous)
    assert out.startswith("'")


def test_formula_safe_leaves_normal_cells():
    assert _formula_safe("Boiler Room") == "Boiler Room"
    assert _formula_safe(None) == ""


# ── A6: upload validation requires a safe extension AND consistent MIME ───────
def test_validate_upload_accepts_pdf():
    storage.validate_upload("report.pdf", "application/pdf")


def test_validate_upload_rejects_exe_even_with_image_mime():
    with pytest.raises(UnsupportedMediaTypeError):
        storage.validate_upload("evil.exe", "image/png")


def test_validate_upload_rejects_pdf_with_executable_mime():
    with pytest.raises(UnsupportedMediaTypeError):
        storage.validate_upload("payload.pdf", "application/x-msdownload")


def test_validate_upload_allows_generic_mime():
    storage.validate_upload("scan.png", "application/octet-stream")


# ── S3: per-IP rate limiter throttles bursts ──────────────────────────────────
async def test_rate_limiter_blocks_after_limit():
    from backend.middleware.rate_limit import RateLimitedError, public_rate_limit

    class _Req:
        def __init__(self, ip):
            self.headers = {}
            self.client = type("C", (), {"host": ip})()

    req = _Req("203.0.113.9")
    limit = Settings().public_rate_limit_per_minute
    for _ in range(limit):
        await public_rate_limit(req)
    with pytest.raises(RateLimitedError):
        await public_rate_limit(req)
