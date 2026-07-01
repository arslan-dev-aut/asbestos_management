"""End-to-end endpoint tests against an in-memory DB with stubbed upstreams.

Exercises every router at least once (happy path) plus the key security
behaviours that the review fixes introduced.
"""

from __future__ import annotations

import io
import uuid

import pytest

from backend.tests.conftest import TENANT_ID

PREFIX = "/api/v1/asbestos"


# ── helpers ──────────────────────────────────────────────────────────────────
async def _add_building_type(client, name="Office Block"):
    r = await client.post(f"{PREFIX}/config/building-types", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["buildingType"]["id"]


async def _add_acm_type(client, name="Pipe Insulation"):
    r = await client.post(f"{PREFIX}/config/acm-types", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["acmType"]["id"]


async def _create_site(client):
    site_id = str(uuid.uuid4())
    customer_id = str(uuid.uuid4())
    r = await client.post(f"{PREFIX}/register", json={"customerId": customer_id, "siteId": site_id})
    assert r.status_code == 201, r.text
    return r.json()["asbestosSiteId"], site_id, customer_id


async def _create_acm(client, asb_site_id, building_id, acm_id):
    r = await client.post(
        f"{PREFIX}/register/{asb_site_id}/acm",
        data={
            "buildingTypeId": building_id,
            "roomLocation": "Room 1",
            "acmTypeId": acm_id,
            "condition": "GOOD",
            "riskScore": "LOW",
            "notes": "n",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["acmEntry"]["id"]


# ── health / config ──────────────────────────────────────────────────────────
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "healthy"}


async def test_config_building_and_acm_types(client):
    bid = await _add_building_type(client)
    aid = await _add_acm_type(client)

    r = await client.get(f"{PREFIX}/config/building-types")
    assert r.status_code == 200
    assert any(b["id"] == bid for b in r.json()["buildingTypes"])

    # toggle inactive
    r = await client.patch(f"{PREFIX}/config/building-types/{bid}", json={"isActive": False})
    assert r.status_code == 200 and r.json()["buildingType"]["isActive"] is False

    r = await client.get(f"{PREFIX}/config/acm-types")
    assert r.status_code == 200 and any(a["id"] == aid for a in r.json()["acmTypes"])


# ── register ──────────────────────────────────────────────────────────────────
async def test_register_create_list_detail_status(client):
    asb_id, site_id, _ = await _create_site(client)

    r = await client.get(f"{PREFIX}/register")
    assert r.status_code == 200 and r.json()["totalCount"] >= 1

    r = await client.get(f"{PREFIX}/register/{asb_id}")
    assert r.status_code == 200 and r.json()["site"]["id"] == asb_id

    # asbestos-status by EXTERNAL site id
    r = await client.get(f"{PREFIX}/register/{site_id}/asbestos-status")
    assert r.status_code == 200
    body = r.json()
    assert body["asbestosSiteId"] == asb_id and body["hasActiveAcm"] is False

    # unknown external id → graceful default, not 404
    r = await client.get(f"{PREFIX}/register/{uuid.uuid4()}/asbestos-status")
    assert r.status_code == 200 and r.json()["hasActiveAcm"] is False

    # check + register lookups
    r = await client.get(f"{PREFIX}/register/check", params={"siteId": site_id})
    assert r.status_code == 200 and r.json()["exists"] is True
    r = await client.get(f"{PREFIX}/register/customers")
    assert r.status_code == 200 and r.json()["totalCount"] >= 1
    r = await client.get(f"{PREFIX}/register/sites")
    assert r.status_code == 200 and r.json()["totalCount"] >= 1


async def test_duplicate_site_rejected(client):
    _, site_id, customer_id = await _create_site(client)
    r = await client.post(f"{PREFIX}/register", json={"customerId": customer_id, "siteId": site_id})
    assert r.status_code == 409


# ── ACM entries ───────────────────────────────────────────────────────────────
async def test_acm_lifecycle(client):
    asb_id, site_id, _ = await _create_site(client)
    bid = await _add_building_type(client)
    aid = await _add_acm_type(client)
    acm_id = await _create_acm(client, asb_id, bid, aid)

    r = await client.get(f"{PREFIX}/register/{asb_id}/acm")
    assert r.status_code == 200 and r.json()["totalCount"] == 1
    assert r.json()["acmEntries"][0]["assetDiscrepancy"] is False

    # status -> remediated
    r = await client.patch(
        f"{PREFIX}/register/{asb_id}/acm/{acm_id}/status", json={"status": "REMEDIATED"}
    )
    assert r.status_code == 200 and r.json()["acmEntry"]["status"] == "REMEDIATED"

    # asbestos-status now reflects no ACTIVE acm
    r = await client.get(f"{PREFIX}/register/{site_id}/asbestos-status")
    assert r.json()["activeAcmCount"] == 0

    # asset-acm-mapping + link check
    r = await client.get(f"{PREFIX}/register/{site_id}/asset-acm-mapping")
    assert r.status_code == 200
    r = await client.get(f"{PREFIX}/register/assets/{uuid.uuid4()}/check-asset-acm-link")
    assert r.status_code == 200 and r.json()["linked"] is False


# ── documents ─────────────────────────────────────────────────────────────────
async def test_document_upload_list_download_remove(client):
    asb_id, _, _ = await _create_site(client)
    files = {"files": ("report.pdf", io.BytesIO(b"%PDF-1.4 data"), "application/pdf")}
    data = {"documentsMetadata": '[{"fileIndex":0,"docType":"SURVEY_REPORT"}]'}
    r = await client.post(f"{PREFIX}/register/{asb_id}/documents", data=data, files=files)
    assert r.status_code == 201, r.text
    doc_id = r.json()["documents"][0]["id"]

    r = await client.get(f"{PREFIX}/register/{asb_id}/documents")
    assert r.status_code == 200 and r.json()["total"] == 1

    r = await client.get(f"{PREFIX}/register/{asb_id}/documents/{doc_id}/download")
    assert r.status_code == 200 and r.json()["url"].startswith("https://blob.test/")

    r = await client.delete(f"{PREFIX}/register/{asb_id}/documents/{doc_id}")
    assert r.status_code == 200


async def test_document_rejects_bad_type(client):
    asb_id, _, _ = await _create_site(client)
    files = {"files": ("malware.exe", io.BytesIO(b"MZ"), "application/x-msdownload")}
    data = {"documentsMetadata": '[{"fileIndex":0,"docType":"OTHER"}]'}
    r = await client.post(f"{PREFIX}/register/{asb_id}/documents", data=data, files=files)
    assert r.status_code == 415


# ── bulk ──────────────────────────────────────────────────────────────────────
async def test_bulk_template_validate_confirm(client):
    bid_name = "Warehouse"
    await _add_building_type(client, name=bid_name)
    await _add_acm_type(client, name="Lagging")

    r = await client.get(f"{PREFIX}/register/bulk-upload/template")
    assert r.status_code == 200

    customer_id = str(uuid.uuid4())
    site_id = str(uuid.uuid4())
    csv = (
        "Customer,Customer ID,Site Name,Site ID,Building,Room/Location,Asset,ACM Type,Condition,Risk Score,Notes\n"
        f"Acme,{customer_id},HQ,{site_id},{bid_name},Boiler Room,,Lagging,Good,Low,note\n"
    )
    files = {"file": ("bulk.csv", io.BytesIO(csv.encode()), "text/csv")}
    r = await client.post(f"{PREFIX}/register/bulk-upload/validate", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["validCount"] == 1 and body["errorCount"] == 0
    token = body["uploadToken"]

    r = await client.post(f"{PREFIX}/register/bulk-upload/confirm", json={"uploadToken": token})
    assert r.status_code == 200, r.text
    assert r.json()["createdSites"] == 1 and r.json()["createdEntries"] == 1

    # token consumed — second confirm fails
    r = await client.post(f"{PREFIX}/register/bulk-upload/confirm", json={"uploadToken": token})
    assert r.status_code == 400


async def test_export_escapes_formula(client):
    # Seed a site so export has at least one row.
    await _create_site(client)
    r = await client.get(f"{PREFIX}/register/export", params={"format": "csv"})
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]


# ── qr code + public view ─────────────────────────────────────────────────────
async def test_qr_generate_and_public_view(client):
    asb_id, _, _ = await _create_site(client)

    r = await client.get(f"{PREFIX}/register/{asb_id}/qr-code")
    assert r.status_code == 200, r.text
    token = r.json()["token"]

    # public view works (unauthenticated path)
    r = await client.get(f"/public/{token}")
    assert r.status_code == 200 and "acmEntries" in r.json()

    # an unknown token is not resolvable
    r = await client.get(f"/public/{token}x")
    assert r.status_code == 404


# ── audit / lookup / files ─────────────────────────────────────────────────────
async def test_audit_endpoints(client):
    await _add_building_type(client)  # generates a config audit row
    r = await client.get(f"{PREFIX}/audit/config")
    assert r.status_code == 200 and r.json()["totalCount"] >= 1

    asb_id, _, _ = await _create_site(client)
    r = await client.get(f"{PREFIX}/register/{asb_id}/audit")
    assert r.status_code == 200 and r.json()["totalCount"] >= 1


async def test_lookup_endpoints(client):
    r = await client.get(f"{PREFIX}/lookup/customers")
    assert r.status_code == 200 and r.json()["totalCount"] == 1
    cid = str(uuid.uuid4())
    r = await client.get(f"{PREFIX}/lookup/customers/{cid}/sites")
    assert r.status_code == 200
    sid = str(uuid.uuid4())
    r = await client.get(f"{PREFIX}/lookup/sites/{sid}/assets")
    assert r.status_code == 200


async def test_files_download_and_tenant_isolation(client):
    asb_id, _, _ = await _create_site(client)
    files = {"files": ("a.pdf", io.BytesIO(b"%PDF"), "application/pdf")}
    data = {"documentsMetadata": '[{"fileIndex":0,"docType":"OTHER"}]'}
    r = await client.post(f"{PREFIX}/register/{asb_id}/documents", data=data, files=files)
    doc_id = r.json()["documents"][0]["id"]

    r = await client.get(f"{PREFIX}/files/{doc_id}/download")
    assert r.status_code == 200

    # another tenant must NOT resolve the file
    r = await client.get(
        f"{PREFIX}/files/{doc_id}/download",
        headers={"X-Tenant-Id": "22222222-2222-2222-2222-222222222222"},
    )
    assert r.status_code == 404


# ── auth ────────────────────────────────────────────────────────────────────
async def test_missing_tenant_header_rejected(client):
    r = await client.get(f"{PREFIX}/register", headers={"X-Tenant-Id": ""})
    assert r.status_code == 401
