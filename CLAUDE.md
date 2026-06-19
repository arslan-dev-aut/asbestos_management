# Joblogic Automation DevContainer

## Overview

This DevContainer is the **standard development environment** for the Joblogic Automation team. It provides everything needed to build, test, and debug automations that extend Joblogic's functionality.

A developer provides **functional requirements** (what the automation should do), and the coding agent uses the skills, context docs, and MCP tools to build the right type of automation.

---

## Automation Types

The team builds **three types** of automations:

### 1. Backend Automations (Webhook & Timer)
- **Webhook**: Endpoint that JobLogic calls when an event occurs (e.g., job completed → sync invoice)
- **Timer**: Runs on a cron schedule via APScheduler (e.g., nightly client sync)
- **Single-tenant** — tenant ID from `.env`
- No frontend — backend only

### 2. JavaScript-Injected Automations
- Inject custom UI components into existing `go.joblogic.com` pages
- Dev workflow: Playwright inspection → vanilla JS authoring → manual CDN upload
- Backend endpoint called from the injected JS
- **Single-tenant** — tenant ID from `.env`

### 3. Marketplace App Automations
- Standalone apps with Vue 3 frontend + FastAPI backend
- Authenticated via JobLogic Identity Server (OAuth2 Authorization Code + PKCE)
- Reuse JobLogic Web components from CDN for consistent UI
- Can be embedded as iframes in `go.joblogic.com`
- **Multi-tenant** — tenant ID from IDP JWT token

---

## Tech Stack

| Layer | Technology | Port |
|-------|------------|------|
| Backend | FastAPI + aiohttp + asyncpg | 8000 |
| Frontend | Vue 3 + Vite + TypeScript | 5173 |
| Database | Azure PostgreSQL (via asyncpg) | — |
| Audit DB | Cosmos DB (MongoDB API, via motor) | — |
| Scheduler | APScheduler AsyncIOScheduler | — |
| Page Inspection | Playwright MCP + Chrome DevTools MCP (dev-time) | — |
| Auth (marketplace) | oidc-client-ts + JobLogic IDP | — |
| Config Store | Azure App Configuration (credentials via `AppConfigManager`) | — |
| Hosting | Azure Container Apps (Workload Profiles Env, Consumption profile) | 8000 |
| Networking | VNet + NAT Gateway (static outbound IP for whitelisting) | — |
| Registry | Azure Container Registry (Basic) | — |
| CI/CD | Azure DevOps Pipelines (`pipelines/deploy-automation.yml`) | — |
| IaC | Bicep (`infra/main.bicep`, `infra/container-app.bicep`) | — |
| SDK | `joblogic-automation-sdk` (JicroClient, ODataClient, config, db, notifications, audit, auth, app_config, models) | — |

---

## Directory Structure

```
├── backend/              # FastAPI backend (CORS, business logic, route handlers)
│   ├── main.py           # FastAPI app entrypoint (port 8000)
│   ├── __init__.py
│   ├── routes/           # Automation-specific route handlers
│   │   ├── __init__.py
│   │   └── automations.py
│   └── utils/            # Project-specific utilities (if any)
│       └── __init__.py
├── frontend/             # Vue 3 + Vite + TypeScript SPA
├── js/                   # JavaScript files for CDN (JS-injected automations)
├── infra/                # Azure Bicep infrastructure-as-code
│   ├── main.bicep        # Core infra: VNet, NAT Gateway, Container Apps Env, ACR
│   └── container-app.bicep # Deploy a single automation as a Container App
├── pipelines/            # Azure DevOps CI/CD templates
│   └── deploy-automation.yml # Reusable pipeline: build → push → deploy
├── context-doc/          # Context documents for the coding agent
├── .claude/              # Skills, rules, agents
├── .devcontainer/        # VS Code Dev Container configuration
├── .vscode/              # Debug configurations
├── docker-compose.yml    # Local service orchestration
├── .env.example          # Environment variable template
└── CLAUDE.md             # This file
```

**Note:** `config.py`, `jicro_client.py`, `db.py`, `utils/notifications.py`, `utils/execution_result.py`, `utils/audit_logger.py`, `routes/audit.py`, and `middleware/auth.py` are **no longer in `backend/`** — they are provided by the `joblogic-automation-sdk` package.

---

## Context Documents

Domain knowledge for building automations:

- @context-doc/automations-overview.md — The 3 automation types & decision tree
- @context-doc/jicro-guide.md — Jicro API reference & JicroClient usage
- @context-doc/azure-sql-guide.md — PostgreSQL with asyncpg
- @context-doc/js-injection-guide.md — JS injection workflow & conventions
- @context-doc/marketplace-apps-guide.md — Marketplace app architecture & IDP
- @context-doc/odata-guide.md — OData proxy endpoint & ODataClient usage
- @context-doc/audit-and-notifications-guide.md — Slack/Teams notifications & Cosmos DB audit logging
- @context-doc/app-config-guide.md — Azure App Configuration for credential management
- @context-doc/deployment-guide.md — Production deployment: Container Apps, NAT Gateway, CI/CD
- @context-doc/project-structure.md — Directory layout & file placement

---

## Skills

| Skill | Description |
|-------|-------------|
| `create-backend-automation` | Create webhook or timer-based backend automations |
| `create-js-injected-automation` | Create JS-injected automations (Playwright → JS → CDN → backend) |
| `create-marketplace-app-automation` | Create marketplace apps (Vue + FastAPI + IDP) |
| `connect-database` | Set up PostgreSQL database with asyncpg |
| `audit-logs` | Add Slack/Teams notifications and Cosmos DB audit logging |
| `frontend-vue-pages` | Create Vue pages using JobLogic CDN components |
| `local-debugging` | Run and debug the full stack locally |

---

## Agents

| Agent | Specialisation |
|-------|---------------|
| `backend-automation-dev` | Webhook & timer backend automations |
| `js-injection-dev` | JavaScript-injected automations |
| `marketplace-app-dev` | Marketplace apps (Vue + FastAPI + IDP) |

---

## MCP Tools

Four MCP servers are connected:

### Joblogic Endpoint Documentation
1. `search_endpoint` — search for Jicro messages by natural language (e.g., `{"query": "search jobs", "limit": 10}`)
2. `get_endpoint` — get full documentation for a specific message (e.g., `{"message_name": "SearchJobMsg"}`)

**Always use MCP tools first** before implementing any Jicro call.

### Playwright MCP
Used during JS-injected automation development to navigate `go.joblogic.com` pages, inspect DOM structure, take screenshots, and identify injection points. This is a **dev-time tool for the AI agent** — not a code dependency.

### Chrome DevTools MCP
Used to inspect running pages, check network requests, and debug JavaScript in the browser. Complements Playwright MCP for JS injection development.

### Context7 MCP
Used to fetch up-to-date documentation for libraries and frameworks during development.

---

## Quick Commands

```bash
# Backend
cd backend && uvicorn main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Run tests
cd backend && pytest
```

---

## Development Rules

1. **Always use MCP tools first** — search and get endpoint docs before writing any Jicro call.
2. **Use `JicroClient`** from `joblogic_sdk.jicro` for all Jicro interactions. **Use `ODataClient`** from `joblogic_sdk.odata` for OData queries and counts.
3. **Tenant ID handling**:
   - Backend & JS-injected automations: single-tenant, `get_settings().tenant_id` via `joblogic_sdk.config`
   - Marketplace apps: multi-tenant, extracted from IDP JWT token via `get_tenant_id` from `joblogic_sdk.auth`
   - Never hardcode a tenant GUID.
4. **Async all the way** — all route handlers, Jicro calls, and DB operations must be `async`.
5. **Database**: Use `query()` and `execute()` from `joblogic_sdk.db`. Parameterised queries only. Each automation gets its own database: `automation-<name>`.
6. **Notifications**: Use `@slack_notification()` / `@teams_notification()` from `joblogic_sdk.notifications`. Return `ExecutionResult` from `joblogic_sdk.models`. Notifications are **decoupled from audit** — use `@audit_log` separately.
7. **Audit logging**: Use `@audit_log` decorator from `joblogic_sdk.audit` for automatic audit logging. Use `AuditManager` from `joblogic_sdk.audit` for custom entries. Audit uses Cosmos DB (MongoDB API) via motor — call `AuditManager.initialize()` at startup and `.shutdown()` at teardown.
8. **Pydantic models** — define request/response models for every endpoint.
9. **CORS** — configured in `backend/main.py`. Add `https://go.joblogic.com` to allowed origins for JS-injected automations.
10. **Vue Composition API** — always use `<script setup lang="ts">` in Vue components.
11. **Environment config** — use `get_settings()` from `joblogic_sdk.config` and `.env`. Never scatter magic strings. In production, credentials are loaded from Azure App Config at startup via `AppConfigManager.load()`. In development, use local `.env` and sync to App Config with `AppConfigManager.sync()`.
12. **SDK-provided modules** — `JicroClient`, `ODataClient`, config, DB helpers, notifications, audit, auth middleware, `AppConfigManager`, `ExecutionResult`, common enums all come from `joblogic-automation-sdk`. Do not recreate these in `backend/`.
13. **`backend/` directory** should only contain: `main.py`, `routes/` (automation-specific handlers), `__init__.py` files, and `utils/__init__.py` for project-specific utilities.

---

## Import Reference

| What | Import |
|------|--------|
| Jicro client | `from joblogic_sdk.jicro import JicroClient, JicroError` |
| OData client | `from joblogic_sdk.odata import ODataClient, ODataError` |
| Configuration | `from joblogic_sdk.config import get_settings` |
| Database helpers | `from joblogic_sdk.db import query, execute` |
| Notifications | `from joblogic_sdk.notifications import slack_notification, teams_notification` |
| Execution result | `from joblogic_sdk.models import ExecutionResult` |
| Audit logging | `from joblogic_sdk.audit import AuditManager, audit_log` |
| Auth middleware | `from joblogic_sdk.auth import get_tenant_id` |
| App Config | `from joblogic_sdk.app_config import AppConfigManager` |

---

## Environment Variables

See `.env.example` for the complete template. Key variables:

| Variable | Used By | Description |
|----------|---------|-------------|
| `AZURE_APP_CONFIG_CONNECTION_STRING` | Backend | Azure App Config connection string |
| `AUTOMATION_NAME` | Backend | Automation name (key prefix in App Config) |
| `TENANT_ID` | Backend, JS-injected | Single-tenant automations |
| `JICRO_BASE_URL` | Backend | Jicro API base URL |
| `JICRO_AUTH_TOKEN` | Backend | Jicro auth token |
| `DATABASE_URL` | Backend | PostgreSQL database |
| `AUDIT_MONGODB_CONNECTION_STRING` | Backend | Cosmos DB (MongoDB API) connection string for audit logging |
| `AUDIT_DB_NAME` | Backend | Cosmos DB database name for audit |
| `AUDIT_COLLECTION_NAME` | Backend | Cosmos DB collection name for audit |
| `SLACK_ENABLED` | Backend | Enable Slack notifications |
| `SLACK_SUCCESS_WEBHOOK` | Backend | Slack success webhook |
| `SLACK_FAILURE_WEBHOOK` | Backend | Slack failure webhook |
| `SLACK_PARTIAL_FAILURE_WEBHOOK` | Backend | Slack partial failure webhook |
| `TEAMS_ENABLED` | Backend | Enable Teams notifications |
| `TEAMS_WORKFLOW_URL` | Backend | Teams workflow webhook |
| `APPLICATION_ENVIRONMENT` | Backend | Environment name |
| `IDP_CLIENT_ID` | Frontend, Backend | OAuth2 client ID (marketplace) |
| `IDP_AUTHORITY` | Frontend, Backend | IDP authority URL (marketplace) |
| `SCHEDULER_CRON_HOUR` | Backend | Timer automation schedule |
| `SCHEDULER_CRON_MINUTE` | Backend | Timer automation schedule |
