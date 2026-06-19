---
paths:
  - "backend/**"
---

# Backend Development Rules

- **Framework**: FastAPI with Python 3.11+
- **All route handlers must be `async`**
- **Use `JicroClient`** from `joblogic_sdk.jicro` for all Joblogic service calls — never create ad-hoc HTTP calls. **Use `ODataClient`** from `joblogic_sdk.odata` for OData queries and counts.
- **Pydantic models**: Define `BaseModel` request/response models for every endpoint
- **Tenant ID**: Single-tenant automations load via `get_settings().tenant_id` from `joblogic_sdk.config`. Marketplace apps extract tenant from the `X-Tenant-Id` header using `get_tenant_id` from `joblogic_sdk.auth`. Never hardcode a tenant GUID.
- **Error handling**: Catch `JicroError` / `ODataError` and re-raise as `HTTPException`
- **Configuration**: Use `get_settings()` from `joblogic_sdk.config` (lazy-loading singleton) for base URLs, tokens, and tenant ID — no magic strings
- **Database**: Use `asyncpg` with parameterized queries (`$1, $2, $3` placeholders) — never concatenate SQL. Use `query()` and `execute()` from `joblogic_sdk.db`. asyncpg is natively async — no `asyncio.to_thread()` for DB calls.
- **Notifications**: Use `@slack_notification()` or `@teams_notification()` from `joblogic_sdk.notifications` on processing functions. Return `ExecutionResult` from `joblogic_sdk.models`. Notifications are decoupled from audit — use `@audit_log` decorator separately for audit logging.
- **Audit logging**: Use `@audit_log` decorator from `joblogic_sdk.audit` for automatic audit logging. Use `AuditManager` from `joblogic_sdk.audit` for custom entries. Audit uses Cosmos DB (MongoDB API) via motor — call `AuditManager.initialize()` at startup and `.shutdown()` at teardown.
- **Timer automations**: Use APScheduler `AsyncIOScheduler` registered in `backend/main.py` lifespan. Cron config from env vars — never hardcode schedules.
- **Imports**: Use `from joblogic_sdk.xxx import ...` for SDK-provided modules. Use `from backend.xxx import ...` only for project-specific code (routes, custom utils).
- **New route files**: Register them in `backend/main.py` with `app.include_router()`
- **CORS**: Configured in `backend/main.py`. Add `https://go.joblogic.com` to allowed origins for JS-injected automations.
- **Auth headers**: For marketplace apps, accept `Authorization` and `X-Tenant-Id` headers from the frontend request. Use `get_tenant_id` from `joblogic_sdk.auth` for tenant extraction.
- **iframe headers**: For marketplace apps embedded in JobLogic, add `Content-Security-Policy: frame-ancestors 'self' https://go.joblogic.com`
- **SDK-provided modules** (do NOT create these in `backend/`): JicroClient, ODataClient, config, DB helpers, notifications, audit, auth middleware, ExecutionResult, common enums — all come from `joblogic-automation-sdk`.
- **`backend/` directory** should only contain: `main.py`, `routes/` (automation-specific route handlers), `__init__.py` files, and `utils/__init__.py` for project-specific utilities.
