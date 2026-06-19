# Azure App Configuration Guide

## Overview

Automation credentials are stored in **Azure App Configuration** using the key format:

```
Automation/<AutomationName>/<ENV_VAR_NAME>
```

For example, an automation called `invoice-sync` would have keys like:
- `Automation/invoice-sync/JICRO_AUTH_TOKEN`
- `Automation/invoice-sync/TENANT_ID`
- `Automation/invoice-sync/DATABASE_URL`

The `AppConfigManager` in `joblogic_sdk.app_config` handles loading and syncing these values.

## How It Works

### Production

At startup, `AppConfigManager.load()` reads all keys matching `Automation/<name>/*` from Azure App Config and injects them into `os.environ`. The existing `get_settings()` singleton then reads them transparently — no changes needed to business logic.

### Development

Use local `.env` files as before. Optionally sync local values to App Config using `AppConfigManager.sync()` so they're available in production.

## Setup

### Environment Variables

Two env vars control App Config itself (these go in `.env`, not in App Config):

```env
AZURE_APP_CONFIG_CONNECTION_STRING=Endpoint=https://<name>.azconfig.io;Id=<id>;Secret=<secret>
AUTOMATION_NAME=<automation-name>
```

### FastAPI Lifespan Integration

Load credentials from App Config at application startup:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from joblogic_sdk.app_config import AppConfigManager
from joblogic_sdk.config import get_settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # In production, load credentials from App Config
    if settings.application_environment == "production":
        await AppConfigManager.load()
    yield

app = FastAPI(lifespan=lifespan)
```

After `AppConfigManager.load()` runs, all env vars (like `JICRO_AUTH_TOKEN`, `TENANT_ID`, etc.) are available via `get_settings()` as usual.

## Using AppConfigManager

### Load (Production)

```python
from joblogic_sdk.app_config import AppConfigManager

# Reads AUTOMATION_NAME and AZURE_APP_CONFIG_CONNECTION_STRING from env
count = await AppConfigManager.load()

# Or pass explicitly
count = await AppConfigManager.load(
    automation_name="invoice-sync",
    connection_string="Endpoint=https://...",
)
```

### Sync (Development)

Push local env vars to App Config so they're available in production:

```python
from joblogic_sdk.app_config import AppConfigManager

await AppConfigManager.sync(
    env_vars={
        "JICRO_AUTH_TOKEN": "secret-token",
        "TENANT_ID": "tenant-guid",
        "DATABASE_URL": "Driver={ODBC Driver 18};...",
        "SLACK_ENABLED": "true",
        "SLACK_SUCCESS_WEBHOOK": "https://hooks.slack.com/...",
    },
    automation_name="invoice-sync",
    connection_string="Endpoint=https://...",
)
```

### Delete

Remove specific keys from App Config:

```python
from joblogic_sdk.app_config import AppConfigManager

await AppConfigManager.delete(
    env_vars=["OLD_SECRET", "DEPRECATED_KEY"],
    automation_name="invoice-sync",
    connection_string="Endpoint=https://...",
)
```

## Key Format Convention

| Key in App Config | Env Var Set |
|-------------------|-------------|
| `Automation/invoice-sync/JICRO_AUTH_TOKEN` | `JICRO_AUTH_TOKEN` |
| `Automation/invoice-sync/TENANT_ID` | `TENANT_ID` |
| `Automation/invoice-sync/DATABASE_URL` | `DATABASE_URL` |
| `Automation/invoice-sync/SLACK_ENABLED` | `SLACK_ENABLED` |

## Development vs Production Flow

| Environment | Credential Source | App Config Role |
|-------------|-------------------|-----------------|
| **Development** | Local `.env` file | Optional sync target (`AppConfigManager.sync()`) |
| **Production** | Azure App Config | Primary source (`AppConfigManager.load()` at startup) |

## Required Dependency

App Config support requires the `appconfig` optional dependency:

```
pip install joblogic-automation-sdk[appconfig]
```

Or use `[all]` which includes it:

```
pip install joblogic-automation-sdk[all]
```
