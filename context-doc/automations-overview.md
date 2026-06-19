# Joblogic Automations Overview

## What is a Joblogic Automation?

An automation is a self-contained application that extends Joblogic's functionality by interacting with Joblogic backend services through the **exec-jicro** endpoint. The Automation team builds three distinct types of automations.

---

## Automation Types

### 1. Backend Automations (Webhook & Timer)

Backend automations have **no frontend** — they are pure FastAPI services that process data.

#### Webhook-Based
- **Trigger**: JobLogic fires a POST to your endpoint when a specific action occurs in the system
- **Example**: "When a job is completed, sync the invoice to Xero"
- **Subscription**: Manual — the webhook URL is registered in the JobLogic admin panel
- **Tenant**: Single-tenant — tenant ID from `.env`

#### Timer-Based
- **Trigger**: APScheduler `AsyncIOScheduler` runs the function on a cron schedule inside the FastAPI process
- **Example**: "Every night at 2 AM, sync all new clients to the CRM"
- **Schedule**: Cron expression stored in environment variables (not hardcoded)
- **Tenant**: Single-tenant — tenant ID from `.env`

**Architecture:**
```
[JobLogic / Cron] → [FastAPI Backend :8000] → [Joblogic exec-jicro]
```

### 2. JavaScript-Injected Automations

JS-injected automations add **custom UI components** to existing pages on `go.joblogic.com`.

- **How it works**: A JavaScript file is hosted on the JobLogic CDN. When a customer loads the target page, the script injects a custom component into the DOM.
- **Development workflow**: Use **Playwright MCP** (dev-time AI agent tool) to inspect the target page → author a vanilla JS file (IIFE pattern) → the JS calls a backend API endpoint for data and actions
- **CDN upload**: Manual — coordinate with DevOps
- **Backend**: Same pattern as webhook-based — a FastAPI endpoint is created for the JS to call
- **Tenant**: Single-tenant — tenant ID from `.env`

**Architecture:**
```
[go.joblogic.com + injected JS] → [FastAPI Backend :8000] → [Joblogic exec-jicro]
```

### 3. Marketplace App Automations

Marketplace apps are **standalone applications** with a Vue 3 frontend and FastAPI backend, authenticated via the JobLogic Identity Server.

- **Frontend**: Vue 3 + TypeScript, uses JobLogic CDN components for consistent look-and-feel
- **Authentication**: OAuth2 Authorization Code + PKCE via `developer.joblogic.com`
- **Embedding**: Can be embedded as an iframe inside `go.joblogic.com`
- **Tenant**: Multi-tenant — tenant ID extracted from the IDP JWT token after user login

**Architecture:**
```
[Vue 3 Frontend :5173] → [FastAPI Backend :8000] → [Joblogic exec-jicro]
```

---

## Which Type Should I Build?

| Requirement | Automation Type |
|-------------|----------------|
| React to an event in JobLogic (job completed, invoice created, etc.) | **Backend — Webhook** |
| Run a batch process on a schedule (nightly sync, daily report) | **Backend — Timer** |
| Add a button, panel, or widget to an existing JobLogic Web page | **JS-Injected** |
| Build a standalone app with its own UI, accessible by multiple tenants | **Marketplace App** |
| Build an app embedded inside JobLogic as a tab / iframe | **Marketplace App** |

---

## Common Infrastructure

All automation types share:

| Component | Details |
|-----------|---------|
| **Backend framework** | FastAPI (Python 3.11+, fully async) |
| **Jicro client** | `joblogic_sdk.jicro` — wraps exec-jicro endpoint |
| **OData client** | `joblogic_sdk.odata` — wraps OData proxy endpoints (query & count) |
| **Database** | Azure PostgreSQL via asyncpg (one DB per automation: `automation-<name>`) |
| **Notifications** | Slack / Teams decorators in `joblogic_sdk.notifications` |
| **Audit logging** | Cosmos DB (MongoDB API) via `joblogic_sdk.audit` (`AuditManager`) |
| **Hosting** | Azure Container Apps (Workload Profiles Env, Consumption profile) |
| **Networking** | VNet + NAT Gateway → single static outbound IP for whitelisting |
| **Registry** | Azure Container Registry (images: `automation-<name>`) |
| **CI/CD** | Azure DevOps Pipelines (`pipelines/deploy-automation.yml`) |
| **IaC** | Bicep templates in `infra/` |

See @context-doc/deployment-guide.md for full deployment details.

---

## Joblogic API Endpoints

### Exec-Jicro Endpoint

All Joblogic backend service calls (actions, writes, specific messages) go through a single dynamic endpoint:

```
POST https://mainsubsysautomationapi.joblogic.com/api/tenancy/{tenantId}/miscs/exec-jicro
```

### Authentication

| Header                    | Value                              |
|---------------------------|------------------------------------|
| `jl-x-header-token-key`  | (see .env / config.py)             |

### Request Body

```json
{
  "jicroServiceName": "<service>",
  "messageSignature": "<MessageClassName>",
  "payload": { … }
}
```

### Available Services

| Service Name     | Description                    |
|------------------|--------------------------------|
| `core`           | Core business entities         |
| `file`           | File management                |
| `notification`   | Emails, SMS, push notifications|
| `logbook`        | Logbook / activity entries     |
| `contractlayer`  | Contract layer operations      |
| `role`           | User roles and permissions     |
| `license`        | License management             |
| `audit`          | Audit trail                    |
| `docgen`         | Document generation            |

### Message Convention

Message class names follow the `*Msg` pattern (e.g. `SearchRoleMsg`, `SendEmailMsg`, `GetLicenseMsg`). Use the MCP `search_endpoint` tool to discover available messages per service.

### OData Proxy Endpoints

For **read-only queries** (listing, searching, counting entities), use the OData proxy instead of exec-jicro:

```
POST /api/tenancy/{tenantId}/miscs/odata-query   → Fetch records
POST /api/tenancy/{tenantId}/miscs/odata-count   → Count records
```

The `ODataClient` in `joblogic_sdk.odata` wraps these endpoints. It supports any OData entity across all microservices with full OData v4 query syntax ($filter, $select, $orderby, $top, $skip, $expand, $count). See @context-doc/odata-guide.md for full details.
