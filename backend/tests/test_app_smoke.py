"""App-level smoke tests: routing, health, audit taxonomy (no DB hits)."""

from fastapi.testclient import TestClient

from backend.core.enums import AUDIT_ACTIONS_BY_TYPE
from backend.main import app

client = TestClient(app)

EXPECTED_PATHS = {
    ("GET", "/api/v1/asbestos/config/building-types"),
    ("POST", "/api/v1/asbestos/config/building-types"),
    ("PATCH", "/api/v1/asbestos/config/building-types/{type_id}"),
    ("GET", "/api/v1/asbestos/config/acm-types"),
    ("GET", "/api/v1/asbestos/register"),
    ("POST", "/api/v1/asbestos/register"),
    ("GET", "/api/v1/asbestos/register/{asbestos_site_id}"),
    ("POST", "/api/v1/asbestos/register/{asbestos_site_id}/documents"),
    ("DELETE", "/api/v1/asbestos/register/{asbestos_site_id}/documents/{document_id}"),
    ("GET", "/api/v1/asbestos/register/{asbestos_site_id}/documents/{document_id}/download"),
    ("POST", "/api/v1/asbestos/register/{asbestos_site_id}/acm"),
    ("PUT", "/api/v1/asbestos/register/{asbestos_site_id}/acm/{acm_entry_id}"),
    ("PATCH", "/api/v1/asbestos/register/{asbestos_site_id}/acm/{acm_entry_id}/status"),
    ("POST", "/api/v1/asbestos/register/{asbestos_site_id}/acm/{acm_entry_id}/attachments"),
    ("GET", "/api/v1/asbestos/register/bulk-upload/template"),
    ("POST", "/api/v1/asbestos/register/bulk-upload/validate"),
    ("POST", "/api/v1/asbestos/register/bulk-upload/confirm"),
    ("GET", "/api/v1/asbestos/register/export"),
    ("GET", "/api/v1/asbestos/register/{asbestos_site_id}/audit"),
    ("POST", "/api/v1/asbestos/register/{asbestos_site_id}/qr-code"),
    ("GET", "/api/v1/asbestos/register/{asbestos_site_id}/qr-code"),
    ("GET", "/public/{token}"),
}


def _registered() -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for route in app.routes:
        for method in getattr(route, "methods", set()) or set():
            out.add((method, route.path))
    return out


def test_all_expected_routes_registered():
    registered = _registered()
    missing = EXPECTED_PATHS - registered
    assert not missing, f"Missing routes: {missing}"


def test_health_returns_healthy():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


def test_audit_taxonomy_requires_tenant_and_returns_all_types():
    # Dev fallback is on; tenant header stands in for a token.
    resp = client.get(
        "/api/v1/asbestos/audit/taxonomy",
        headers={"X-Tenant-Id": "11111111-1111-1111-1111-111111111111"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    returned_types = {opt["auditType"] for opt in body["taxonomy"]}
    assert returned_types == {t.value for t in AUDIT_ACTIONS_BY_TYPE}


def test_protected_route_without_auth_is_rejected():
    resp = client.get("/api/v1/asbestos/audit/taxonomy")
    assert resp.status_code == 401
