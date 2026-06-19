# OData Proxy Guide

## Overview

The OData Proxy provides two generic endpoints that can query **any OData entity** across all supported microservices without requiring dedicated controller endpoints. Instead of writing new API endpoints for each entity, callers pass a service name, entity name, and raw OData query string.

The `ODataClient` in `joblogic_sdk.odata` wraps these endpoints.

## Endpoints

```
POST /api/tenancy/{tenantId}/miscs/odata-query   → Fetch records
POST /api/tenancy/{tenantId}/miscs/odata-count   → Count records
```

## Authentication

Same as exec-jicro — uses the `jl-x-header-token-key` header with `JICRO_AUTH_TOKEN`.

## Supported Services

| Service Name | Description | Example Entities |
|-------------|-------------|-----------------|
| `core` | Core domain entities | Job, Customer, Site, Visit, Quote, Invoice, Engineer, etc. |
| `file` | File/attachment management | Attachment |
| `logbook` | Logbook and reporting | DynamicDashboardReport, MobileForm |
| `contractlayer` | Contract management | CustomerContract |
| `role` | User roles and access | MobileUser, PortalRole |
| `license` | Licensing and company | Company, Dataset |
| `docgen` | Document generation | ViewDocumentTemplate |
| `hire` | Hire/equipment contracts | HireContract |
| `subcontractor` | Subcontractor management | Job, TenantMapping |
| `utility` | Utility/tasks | ToDo, ToDoAssignToUser |

## Using the ODataClient

```python
from joblogic_sdk.odata import ODataClient, ODataError

# Fetch records
async with ODataClient() as client:
    result = await client.query(
        tenant_id="<tenant-guid>",
        service_name="core",
        entity_name="Job",
        query_string="$filter=StatusId eq 'Y'&$select=Id,StringId,Description&$top=10",
    )
    jobs = result["jicroResponse"]

# Count records
async with ODataClient() as client:
    total = await client.count(
        tenant_id="<tenant-guid>",
        service_name="core",
        entity_name="Job",
        query_string="$filter=StatusId eq 'Y'",
    )
```

## OData Query String Reference

The `query_string` parameter supports standard OData v4 query options:

| Option | Description | Example |
|--------|-------------|---------|
| `$filter` | Filter records | `$filter=StatusId eq 'Y'` |
| `$select` | Select specific fields | `$select=Id,Name,Email` |
| `$orderby` | Sort results | `$orderby=DateLogged desc` |
| `$top` | Limit number of results | `$top=50` |
| `$skip` | Skip N results (pagination) | `$skip=100` |
| `$expand` | Include related entities | `$expand=Customer` |
| `$count` | Include total count | `$count=true` |

**Filter operators:** `eq`, `ne`, `gt`, `ge`, `lt`, `le`, `and`, `or`, `contains()`, `startswith()`

## Entity Name

Either the short name or the full CLR type name is accepted:
- Short: `"Job"`
- Full: `"JobLogic.Microservice.Core.Contract.ODataEdm.Job"`

## Include Soft-Deleted Records

Pass `include_soft_deleted=True` to include soft-deleted records in results.

## Error Handling

`ODataClient` raises `ODataError` with `status` and `detail` attributes:

```python
from fastapi import HTTPException
from joblogic_sdk.odata import ODataClient, ODataError

try:
    async with ODataClient() as client:
        result = await client.query(...)
except ODataError as e:
    raise HTTPException(status_code=e.status, detail=e.detail)
```

## Response Format

### query() Response

```json
{
  "result": true,
  "jicroResponse": [ ... ],
  "log": {
    "jicroServiceName": "core",
    "messageSignature": "ODataFetchTenancyMsg",
    "isJicroCallExecutedSuccessfully": true,
    "logEntries": [ ... ]
  }
}
```

### count() Response

Returns an integer directly (extracted from `jicroResponse`).

## When to Use OData vs exec-jicro

| Use Case | Use |
|----------|-----|
| Query/list/search entities with filtering, sorting, pagination | **ODataClient** |
| Count records matching a condition | **ODataClient** |
| Execute a specific action (create, update, send email, etc.) | **JicroClient** |
| Call a specific message with a custom payload | **JicroClient** |

OData is ideal for **read operations** — fetching and counting data. Use exec-jicro for **write operations** and specific service messages.
