# Deployment Guide

## Overview

Automations are deployed as **Azure Container Apps** running on a **Workload Profiles environment** with a **Consumption profile**. A **NAT Gateway** provides a single static outbound IP for all automations, solving IP whitelisting requirements.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  VNet (10.0.0.0/16)                                     │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Container Apps Environment (Workload Profiles)    │   │
│  │ Consumption Profile (serverless, scale-to-zero)   │   │
│  │                                                    │   │
│  │  [ca-invoice-sync]  [ca-stock-update]  [ca-...]   │   │
│  └──────────────┬───────────────────────────────────┘   │
│                 │ outbound                               │
│  ┌──────────────▼───────────────────────────────────┐   │
│  │ NAT Gateway + Static Public IP                    │   │
│  │ (single fixed IP for ALL outbound traffic)        │   │
│  └──────────────┬───────────────────────────────────┘   │
│                 │                                         │
└─────────────────┼───────────────────────────────────────┘
                  ▼
     Joblogic APIs / Azure PostgreSQL / Cosmos DB
```

## Key Design Decisions

### Why Workload Profiles Environment (not Consumption-only)?

- **Consumption-only environments do NOT support NAT Gateway** — outbound IPs are dynamic and unpredictable
- **Workload Profiles environments** support NAT Gateway for static outbound IP
- Apps still run on the **Consumption profile** within the Workload Profiles environment — same serverless, scale-to-zero, pay-per-use billing
- The environment type controls networking capabilities; the workload profile controls compute billing

### Why NAT Gateway?

- All outbound traffic from every automation routes through **one static public IP**
- Whitelist this single IP with Joblogic APIs, Azure PostgreSQL firewall, Cosmos DB firewall, etc.
- Eliminates the need to track and whitelist dynamic IP ranges

### Scaling by Trigger Type

| Trigger Type | Min Replicas | Max Replicas | Scaling |
|-------------|-------------|-------------|---------|
| `webhook` | 0 (scale to zero) | 2 | HTTP concurrent requests |
| `timer` | 1 (APScheduler must run) | 2 | Fixed |
| `marketplace` | 1 (responsive UI) | 3 | HTTP concurrent requests |

## Infrastructure

All infrastructure is defined in **Bicep** templates in the `infra/` directory:

- `infra/main.bicep` — Core infrastructure (deploy once)
  - VNet with /27 subnet
  - NAT Gateway with static public IP
  - Container Apps Environment (Workload Profiles)
  - Azure Container Registry (Basic)
  - Log Analytics Workspace

- `infra/container-app.bicep` — Individual automation (deploy per automation)
  - Container App on Consumption profile
  - Configured with health probes, App Config secrets, and scaling rules

## CI/CD Pipeline

The `pipelines/deploy-automation.yml` Azure DevOps template handles:

1. **Build** — `az acr build` to build and push the Docker image to ACR
2. **Deploy** — `az deployment group create` with `container-app.bicep`
3. **Verify** — Health check on the deployed app

### Using the pipeline for a new automation

Create an `azure-pipelines.yml` in the automation's repo:

```yaml
trigger:
  branches:
    include: [main]

extends:
  template: pipelines/deploy-automation.yml
  parameters:
    automationName: 'my-automation'
    triggerType: 'webhook'  # or 'timer' or 'marketplace'
```

## Credential Management in Production

1. **Azure App Configuration** stores all automation credentials
2. At container startup, `AppConfigManager.load()` reads keys matching `Automation/<name>/*`
3. Keys are injected into `os.environ` — `get_settings()` reads them transparently
4. Only two env vars are set at the Container App level:
   - `AUTOMATION_NAME` — identifies which keys to load
   - `AZURE_APP_CONFIG_CONNECTION_STRING` — stored as a Container App secret

## Adding a New Automation to Production

1. **Sync credentials** to Azure App Config:
   ```python
   await AppConfigManager.sync(env_vars={...}, automation_name="my-automation")
   ```
2. **Build and push** the Docker image to ACR
3. **Deploy** via the CI/CD pipeline or manually with `container-app.bicep`
4. **No IP whitelisting needed** — the NAT Gateway IP is already whitelisted

## Cost Estimate (50+ automations)

| Component | Monthly Cost |
|-----------|-------------|
| NAT Gateway | ~$32 |
| Static Public IP | ~$3.65 |
| Container Apps (Consumption, mostly idle) | ~$0–20 |
| Log Analytics (30-day retention) | ~$5–15 |
| ACR (Basic tier) | ~$5 |
| **Total** | **~$45–75** |
