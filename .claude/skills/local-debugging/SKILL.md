---
name: local-debugging
description: Set up and run the full automation stack locally for debugging. Covers environment configuration, running all services, and VS Code debugger setup.
argument-hint: <optional — automation name or issue to debug>
---

# Local Debugging

Debug and run the automation locally: $ARGUMENTS

---

## Step 1: Environment Setup

### 1a. Create `.env` file

Copy the template and fill in your values:

```bash
cp .env.example .env
```

### 1b. Required environment variables

```env
# === Tenant (single-tenant automations) ===
TENANT_ID=<your-tenant-guid>

# === Jicro API ===
JICRO_BASE_URL=https://mainsubsysautomationapi.joblogic.com
JICRO_AUTH_TOKEN=<your-auth-token>

# === PostgreSQL Database (if automation uses a database) ===
DATABASE_URL=postgresql://<user>:<password>@<server>.postgres.database.azure.com:5432/automation-<name>?sslmode=require

# === MongoDB Audit Logging (if using audit logs) ===
MONGODB_CONNECTION_STRING=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/<database>?retryWrites=true&w=majority

# === Notifications ===
SLACK_ENABLED=false
SLACK_SUCCESS_WEBHOOK=
SLACK_FAILURE_WEBHOOK=
SLACK_PARTIAL_FAILURE_WEBHOOK=
TEAMS_ENABLED=0
TEAMS_WORKFLOW_URL=
APPLICATION_ENVIRONMENT=development

# === IDP (marketplace apps only) ===
IDP_CLIENT_ID=
IDP_AUTHORITY=
IDP_REDIRECT_URI=http://localhost:5173/callback
IDP_SCOPES=openid profile

# === APScheduler (timer automations only) ===
SCHEDULER_CRON_HOUR=2
SCHEDULER_CRON_MINUTE=0
```

> **Tip:** For local debugging, set `SLACK_ENABLED=false` and `TEAMS_ENABLED=0` to avoid sending real notifications.

---

## Step 2: Install Dependencies

If not already done by the DevContainer setup:

```bash
# Backend
cd /workspace/backend && pip install -r requirements.txt

# Frontend (if marketplace app)
cd /workspace/frontend && npm install
```

---

## Step 3: Run the Services

### Option A: Run individually (recommended for debugging)

Open two terminals:

**Terminal 1 — Backend (port 8000):**

```bash
cd /workspace/backend && uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend (port 5173, marketplace apps only):**

```bash
cd /workspace/frontend && npm run dev
```

### Option B: Docker Compose

```bash
cd /workspace && docker-compose up
```

> **Note:** Docker Compose runs the backend. The frontend dev server is better run separately for hot-reload.

---

## Step 4: VS Code Debugger

### 4a. Python debugger for backend

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Backend (8000)",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--reload", "--port", "8000"],
      "cwd": "${workspaceFolder}/backend",
      "envFile": "${workspaceFolder}/.env",
      "jinja": true
    }
  ]
}
```

### 4b. Set breakpoints

- Open any file under `backend/routes/` or `backend/utils/`
- Click in the gutter to set breakpoints
- Start the "Backend (8000)" debug configuration
- Trigger the endpoint via Swagger UI or a REST client

---

## Step 5: Testing & Verification

### Swagger UI

- **Backend:** `http://localhost:8000/docs`

Provides interactive API documentation where you can test endpoints directly.

### Health checks

```bash
# Backend health
curl http://localhost:8000/health
```

### Run tests

```bash
cd /workspace/backend && pytest
```

### REST Client (VS Code)

Use the **REST Client** extension (already installed). Create a `.http` file:

```http
### Health check
GET http://localhost:8000/health

### Execute a Jicro call
POST http://localhost:8000/api/automations/exec
Content-Type: application/json

{
  "tenant_id": "{{$dotenv TENANT_ID}}",
  "service_name": "core",
  "message_signature": "SearchJobMsg",
  "payload": {
    "searchText": "test",
    "pageSize": 10,
    "pageNumber": 1
  }
}
```

---

## Step 6: Playwright MCP (JS-injected automations)

For JS-injected automation development, use the **Playwright MCP** and **Chrome DevTools MCP** tools (available to the AI agent) to:

- Navigate to `go.joblogic.com` pages and inspect the DOM structure
- Take screenshots to understand the page layout
- Evaluate your JavaScript code on the page to test injection
- Check network requests and debug JS via Chrome DevTools MCP

These are **MCP tools for the AI agent** — not code dependencies. No Playwright installation is needed.

---

## Common Issues

| Issue                                    | Solution                                                                                                                                                                                                                        |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL is not set`                | Ensure `.env` file exists and has the PostgreSQL connection string                                                                                                                                                              |
| `MONGODB_CONNECTION_STRING is not set`   | Only needed if using audit logging — add to `.env`                                                                                                                                                                              |
| Port 8000/5173 already in use            | Check with `lsof -i :<port>` and kill the conflicting process                                                                                                                                                                   |
| `JicroError 401`                         | Check `JICRO_AUTH_TOKEN` in `.env`                                                                                                                                                                                              |
| `JicroError 404`                         | Wrong message signature — use MCP `search_endpoint` to verify                                                                                                                                                                   |
| `CORS error in browser`                  | Check `backend/main.py` CORS `allow_origins` list                                                                                                                                                                               |
| `Module not found: backend.xxx`          | Run from the correct directory (`cd /workspace/backend`) or ensure `PYTHONPATH` includes the workspace root                                                                                                                     |
| Frontend can't reach API                 | Ensure Vite proxy is configured in `vite.config.ts` and backend is running on port 8000                                                                                                                                         |

---

## Quick Reference

| Service  | Port | URL                     | Swagger                      |
| -------- | ---- | ----------------------- | ---------------------------- |
| Backend  | 8000 | `http://localhost:8000` | `http://localhost:8000/docs` |
| Frontend | 5173 | `http://localhost:5173` | —                            |
