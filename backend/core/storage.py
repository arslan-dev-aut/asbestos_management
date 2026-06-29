"""Azure Blob Storage client.

Stores document/attachment binaries and generated QR PNGs, and produces
short-lived download URLs.

Credential selection mirrors postgres.py — explicit rather than relying on
DefaultAzureCredential's full fallback chain:
- Azure (IDENTITY_ENDPOINT present): ManagedIdentityCredential (UAMI)
- Local dev: AzureCliCredential (az login)

An optional connection string (AZURE_STORAGE_CONNECTION_STRING) is supported
for fully local dev without Azure credentials. In that mode SAS tokens are
signed with the storage account key instead of a user-delegation key.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from backend.config import get_settings

_log = logging.getLogger(__name__)
from backend.core.enums import ALLOWED_FILE_EXT, ALLOWED_FILE_MIME
from backend.database.exceptions import UnsupportedMediaTypeError, UpstreamError

_service_client = None  # azure.storage.blob.aio.BlobServiceClient
_credential = None  # azure.identity.aio credential
_ensured_container = False


# ---------------------------------------------------------------------------
# Credential helpers (same explicit pattern as postgres.py)
# ---------------------------------------------------------------------------

def _in_azure() -> bool:
    return bool(os.environ.get("IDENTITY_ENDPOINT"))


def _make_credential():
    """Explicit credential — UAMI in Azure, az login locally."""
    settings = get_settings()
    if _in_azure():
        from azure.identity.aio import ManagedIdentityCredential

        client_id = settings.azure_client_id or None
        return (
            ManagedIdentityCredential(client_id=client_id)
            if client_id
            else ManagedIdentityCredential()
        )
    from azure.identity.aio import AzureCliCredential

    return AzureCliCredential()


# ---------------------------------------------------------------------------
# Upload validation
# ---------------------------------------------------------------------------

def validate_upload(file_name: str, content_type: str | None) -> None:
    """Reject anything that is not PDF/JPEG/PNG (server-side enforcement)."""
    ext = os.path.splitext(file_name or "")[1].lower()
    mime_ok = content_type in ALLOWED_FILE_MIME if content_type else False
    ext_ok = ext in ALLOWED_FILE_EXT
    if not (mime_ok or ext_ok):
        raise UnsupportedMediaTypeError(
            "Unsupported file type. Only PDF, JPEG, and PNG are allowed.",
            detail={"fileName": file_name, "contentType": content_type},
        )


def build_object_key(*parts: str, file_name: str) -> str:
    """Deterministic, collision-resistant blob name."""
    ext = os.path.splitext(file_name)[1].lower()
    prefix = "/".join(str(p).strip("/") for p in parts if p)
    return f"{prefix}/{uuid.uuid4().hex}{ext}"


# ---------------------------------------------------------------------------
# Client initialisation
# ---------------------------------------------------------------------------

def _get_service_client():
    global _service_client, _credential
    if _service_client is None:
        settings = get_settings()
        from azure.storage.blob.aio import BlobServiceClient

        if settings.azure_storage_connection_string:
            _service_client = BlobServiceClient.from_connection_string(
                settings.azure_storage_connection_string
            )
        else:
            _credential = _make_credential()
            parsed = urlparse(settings.azure_storage_account_url)
            account_url = f"{parsed.scheme}://{parsed.netloc}"
            _service_client = BlobServiceClient(
                account_url=account_url, credential=_credential
            )
    return _service_client


def _account_key_from_connection_string(conn: str) -> str | None:
    for part in conn.split(";"):
        if part.strip().lower().startswith("accountkey="):
            return part.split("=", 1)[1]
    return None


async def _ensure_container(client) -> None:
    global _ensured_container
    if _ensured_container:
        return
    from azure.core.exceptions import ResourceExistsError

    try:
        await client.create_container(get_settings().azure_storage_container)
    except ResourceExistsError:
        pass
    except Exception:  # noqa: BLE001 - container may pre-exist / be RBAC-restricted
        pass
    _ensured_container = True


# ---------------------------------------------------------------------------
# Public operations
# ---------------------------------------------------------------------------

async def put_object(key: str, data: bytes, content_type: str | None) -> str:
    """Upload bytes; return the blob name (stored as ``file_url``)."""
    settings = get_settings()
    from azure.storage.blob import ContentSettings

    client = _get_service_client()
    await _ensure_container(client)
    container = client.get_container_client(settings.azure_storage_container)
    try:
        await container.upload_blob(
            name=key,
            data=data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type or "application/octet-stream"),
        )
    except Exception as exc:  # pragma: no cover - network
        raise UpstreamError("Failed to store file.", detail=str(exc)) from exc
    return key


async def presigned_url(key: str) -> str:
    """Short-lived read URL (SAS) for a stored blob.

    Production (Entra auth): user-delegation SAS signed with a key issued by
    the storage service itself — no static secrets needed.
    Local dev (connection string): shared-key SAS signed with the account key.
    """
    settings = get_settings()
    from azure.storage.blob import BlobSasPermissions, generate_blob_sas

    client = _get_service_client()
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=5)
    expiry = now + timedelta(seconds=settings.blob_sas_expiry_seconds)
    container = settings.azure_storage_container

    try:
        if settings.azure_storage_connection_string:
            account_key = _account_key_from_connection_string(
                settings.azure_storage_connection_string
            )
            sas = generate_blob_sas(
                account_name=client.account_name,
                container_name=container,
                blob_name=key,
                account_key=account_key,
                permission=BlobSasPermissions(read=True),
                expiry=expiry,
                start=start,
            )
        else:
            udk = await client.get_user_delegation_key(key_start_time=start, key_expiry_time=expiry)
            sas = generate_blob_sas(
                account_name=client.account_name,
                container_name=container,
                blob_name=key,
                user_delegation_key=udk,
                permission=BlobSasPermissions(read=True),
                expiry=expiry,
                start=start,
            )
    except Exception as exc:  # pragma: no cover - network
        raise UpstreamError("Failed to create download URL.", detail=str(exc)) from exc

    blob_url = f"{client.url.rstrip('/')}/{container}/{key}"
    _log.debug("presigned_url: account=%r container=%r key=%r url=%r", client.account_name, container, key, blob_url)
    return f"{blob_url}?{sas}"


async def public_url(key: str) -> str:
    """Stable URL for embeddable objects (e.g. QR images).

    Uses the configured public base if present, else a SAS URL.
    """
    settings = get_settings()
    if settings.storage_public_base_url:
        return f"{settings.storage_public_base_url.rstrip('/')}/{key}"
    return await presigned_url(key)


async def delete_object(key: str) -> None:
    """Best-effort blob deletion — used to clean up blobs on transaction rollback."""
    try:
        client = _get_service_client()
        settings = get_settings()
        container = client.get_container_client(settings.azure_storage_container)
        await container.delete_blob(key)
    except Exception:  # noqa: BLE001
        pass


async def close_storage() -> None:
    """Release the blob client + credential on application shutdown."""
    global _service_client, _credential, _ensured_container
    if _service_client is not None:
        await _service_client.close()
        _service_client = None
    if _credential is not None:
        await _credential.close()
        _credential = None
    _ensured_container = False
