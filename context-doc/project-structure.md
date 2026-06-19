# Project Structure Guide

## Directory Layout

```
├── backend/                      # FastAPI Backend (CORS, business logic, route handlers)
│   ├── __init__.py
│   ├── main.py                   # FastAPI app entrypoint (port 8000)
│   ├── requirements.txt          # Backend dependencies
│   └── routes/
│       ├── __init__.py
│       └── automations.py        # Automation route handlers
│
├── joblogic_sdk/                 # Shared SDK (installed as package from separate repo)
│   ├── config.py                 # Env var configuration via get_settings()
│   ├── jicro.py                  # Async Jicro client (JicroClient, JicroError)
│   ├── db.py                     # Async database access via asyncpg
│   ├── models.py                 # Shared models (ExecutionResult, etc.)
│   ├── notifications.py          # Slack / Teams notification decorators
│   ├── audit.py                  # Cosmos DB (MongoDB API) audit logging (AuditManager)
│   ├── auth.py                   # JWT validation for marketplace apps
│   └── app_config.py             # Azure App Config credential management (AppConfigManager)
│
├── frontend/                     # Vue 3 + Vite + TypeScript SPA
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.ts               # Vue app entrypoint with router + auth guard
│       ├── App.vue               # Root component
│       ├── auth.ts               # OAuth2 PKCE auth service (marketplace apps)
│       ├── api.ts                # Typed fetch wrapper with auth headers
│       ├── views/                # Page components
│       └── components/           # Shared Vue components
│
├── js/                           # JavaScript files for CDN (JS-injected automations)
│
├── context-doc/                  # Pre-populated context documents
│   ├── automations-overview.md   # The 3 automation types
│   ├── project-structure.md      # This file
│   ├── jicro-guide.md            # Jicro API reference
│   ├── azure-sql-guide.md        # PostgreSQL with asyncpg
│   ├── js-injection-guide.md     # JS injection workflow
│   ├── marketplace-apps-guide.md # Marketplace app architecture
│   ├── audit-and-notifications-guide.md  # Notifications & audit logging
│   └── app-config-guide.md       # Azure App Config credential management
│
├── .claude/                      # Claude Code / Copilot configuration
│   ├── settings.json             # Project-level settings & permissions
│   ├── skills/                   # Invokable skills
│   │   ├── create-backend-automation/    # Webhook + timer automations
│   │   ├── create-js-injected-automation/ # JS injection automations
│   │   ├── create-marketplace-app-automation/ # Marketplace apps
│   │   ├── connect-database/             # PostgreSQL with asyncpg
│   │   ├── audit-logs/                   # Notifications + MongoDB logging
│   │   ├── frontend-vue-pages/           # Vue pages for marketplace apps
│   │   └── local-debugging/              # Local dev & debugging setup
│   ├── rules/                    # Path-scoped coding rules
│   │   ├── backend.md
│   │   └── frontend.md
│   └── agents/                   # Custom subagents
│       ├── backend-automation-dev.md     # Webhook + timer specialist
│       ├── js-injection-dev.md           # JS injection specialist
│       └── marketplace-app-dev.md        # Marketplace app specialist
│
├── .devcontainer/                # VS Code Dev Container
│   ├── devcontainer.json
│   ├── Dockerfile
│   └── post-create.sh
│
├── .vscode/
│   └── launch.json               # Debug configurations
│
├── infra/                        # Azure Bicep infrastructure-as-code
│   ├── main.bicep                # Core infra: VNet, NAT Gateway, Container Apps Env, ACR
│   ├── container-app.bicep       # Deploy a single automation as a Container App
│   └── README.md                 # Deployment instructions & architecture diagram
│
├── pipelines/                    # Azure DevOps CI/CD templates
│   └── deploy-automation.yml     # Reusable pipeline: build → push → deploy
│
├── .mcp.json                     # MCP server config (Joblogic endpoint docs)
├── CLAUDE.md                     # Root instructions
├── docker-compose.yml            # Local service orchestration
├── .env.example                  # Environment variable template
├── .gitignore
└── .dockerignore
```

## Where to Put Things

| What you're adding                     | Where it goes                     |
|----------------------------------------|-----------------------------------|
| New automation endpoint                | `backend/routes/`                 |
| New Vue page                           | `frontend/src/views/`             |
| Shared Vue component                   | `frontend/src/components/`        |
| Pydantic request/response models       | `backend/routes/` (inline) or `backend/models/` |
| Database queries                       | Use `joblogic_sdk.db` helpers     |
| Utility / helper functions             | `backend/utils/`                  |
| JavaScript for CDN injection           | `js/`                             |
| Configuration / env vars               | `joblogic_sdk.config` (`get_settings()`) + `.env` |
| Credential management (App Config)     | Use `joblogic_sdk.app_config` (`AppConfigManager`) |
| Auth middleware (marketplace apps)     | Use `joblogic_sdk.auth`          |
| Infrastructure changes                 | `infra/` (Bicep templates)        |
| CI/CD pipeline changes                 | `pipelines/` (Azure DevOps YAML)  |
