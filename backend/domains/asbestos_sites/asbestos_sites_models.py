"""Pydantic schemas for the asbestos_sites domain.

The GET /asbestos-sites/by-site-id/{site_id} endpoint returns the same
SiteDetailResponse as the register domain's GET /{asbestos_site_id} endpoint.
No new response shapes are defined here — this module re-exports the shared
model for clarity and to keep the domain self-contained.
"""

from backend.domains.register.register_models import SiteDetailResponse  # noqa: F401
