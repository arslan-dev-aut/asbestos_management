# Jicro API Guide

## Overview

All Joblogic backend service calls go through a single dynamic endpoint called **exec-jicro**. The `JicroClient` in `joblogic_sdk.jicro` wraps this endpoint.

## Endpoint

```
POST https://mainsubsysautomationapi.joblogic.com/api/tenancy/{tenantId}/miscs/exec-jicro
```

## Authentication

| Header                   | Value                               |
|--------------------------|-------------------------------------|
| `jl-x-header-token-key`  | Set in `.env` as `JICRO_AUTH_TOKEN` |

## Request Body

```json
{
  "jicroServiceName": "<service>",
  "messageSignature": "<MessageClassName>",
  "payload": { ... }
}
```

## Available Services

| Service Name     | Description                    |
|------------------|--------------------------------|
| `core`           | Core business entities (jobs, clients, engineers, sites) |
| `file`           | File management (upload, download, attachments) |
| `notification`   | Emails, SMS, push notifications |
| `logbook`        | Logbook / activity entries     |
| `contractlayer`  | Contract layer operations      |
| `role`           | User roles and permissions     |
| `license`        | License management             |
| `audit`          | Audit trail                    |
| `docgen`         | Document generation            |

## Message Signature Convention

- All message class names end with `Msg` (e.g. `SearchJobMsg`, `SendEmailMsg`, `GetLicenseMsg`).
- Use the MCP `search_endpoint` tool to discover messages.
- Use the MCP `get_endpoint` tool to get the full payload schema.

## Using the JicroClient

```python
from joblogic_sdk.jicro import JicroClient, JicroError

async with JicroClient() as client:
    result = await client.execute(
        tenant_id="<tenant-guid>",
        service_name="core",
        message_signature="SearchJobMsg",
        payload={
            "searchText": "example",
            "pageSize": 10,
            "pageNumber": 1,
        },
    )
```

## Workflow: Implementing a New Jicro Call

1. **Search** — Use MCP `search_endpoint` with a natural language query to find the right message.
2. **Get Docs** — Use MCP `get_endpoint` with the message name to get the full payload schema.
3. **Define Model** — Create a Pydantic model for the request.
4. **Implement** — Create a route handler that uses `JicroClient.execute()`.
5. **Test** — Use the FastAPI Swagger UI at `/docs` to test.

## Error Handling

`JicroClient` raises `JicroError` with `status` and `detail` attributes. Always catch this and return a proper HTTP error:

```python
from fastapi import HTTPException
from joblogic_sdk.jicro import JicroClient, JicroError

try:
    async with JicroClient() as client:
        result = await client.execute(...)
except JicroError as e:
    raise HTTPException(status_code=e.status, detail=e.detail)
```

## OData Queries

For read-only data fetching (listing, searching, counting entities), use the **OData proxy** instead of exec-jicro. See @context-doc/odata-guide.md for full details.

```python
from joblogic_sdk.odata import ODataClient, ODataError

async with ODataClient() as client:
    result = await client.query(
        tenant_id="<tenant-guid>",
        service_name="core",
        entity_name="Job",
        query_string="$filter=StatusId eq 'Y'&$select=Id,StringId&$top=10",
    )
```

## Tenant ID Handling

- **Backend & JS-injected automations**: Single-tenant — tenant ID from `get_settings().tenant_id` via `joblogic_sdk.config`
- **Marketplace apps**: Multi-tenant — tenant ID extracted from the IDP JWT token and passed via `X-Tenant-Id` header

Never hardcode a tenant GUID.

```python
from fastapi import HTTPException
from joblogic_sdk.jicro import JicroClient, JicroError
from joblogic_sdk.config import get_settings

settings = get_settings()
tenant_id = settings.tenant_id

try:
    async with JicroClient() as client:
        result = await client.execute(...)
except JicroError as e:
    raise HTTPException(status_code=e.status, detail=e.detail)
```
