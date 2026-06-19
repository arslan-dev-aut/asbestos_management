# Infrastructure — Azure Container Apps

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
     (whitelist this one IP)
```

## Files

| File | Purpose |
|------|---------|
| `main.bicep` | Core infrastructure: VNet, NAT Gateway, static IP, Container Apps Environment, ACR, Log Analytics |
| `container-app.bicep` | Deploy a single automation as a Container App |

## Prerequisites

- Azure CLI (`az`) installed and logged in
- A resource group created for the automations

## Deploy Core Infrastructure (one-time)

```bash
az deployment group create \
  --resource-group rg-automations-prod \
  --template-file infra/main.bicep \
  --parameters environmentName=automations-prod location=uksouth
```

Outputs:
- **natGatewayPublicIp** — the static IP to whitelist with Joblogic and other external services
- **containerAppsEnvironmentId** — used when deploying individual automations
- **acrLoginServer** — Docker registry URL

## Deploy an Automation

### 1. Build and push the Docker image

```bash
az acr build \
  --registry <acr-name> \
  --image automation-invoice-sync:latest \
  ./backend
```

### 2. Deploy the Container App

```bash
az deployment group create \
  --resource-group rg-automations-prod \
  --template-file infra/container-app.bicep \
  --parameters \
    automationName=invoice-sync \
    containerAppsEnvironmentId=<env-resource-id> \
    acrLoginServer=<acr>.azurecr.io \
    triggerType=webhook \
    appConfigConnectionString=<connection-string>
```

### Trigger Types

| Type | Min Replicas | Scaling | Use For |
|------|-------------|---------|---------|
| `webhook` | 0 (scale to zero) | HTTP concurrent requests | Event-driven automations |
| `timer` | 1 (always running) | Fixed | APScheduler-based cron automations |
| `marketplace` | 1 (always running) | HTTP (up to 3) | Marketplace apps with UI |

## Cost Estimate (50+ automations)

| Component | Monthly Cost |
|-----------|-------------|
| NAT Gateway | ~$32 |
| Static Public IP | ~$3.65 |
| Consumption profile apps (mostly idle) | ~$0–20 |
| Log Analytics (30-day retention) | ~$5–15 |
| ACR (Basic tier) | ~$5 |
| **Total** | **~$45–75** |

## IP Whitelisting

After deploying `main.bicep`, note the `natGatewayPublicIp` output. This single static IP is used for **all** outbound traffic from every automation. Whitelist it with:

- Joblogic exec-jicro / OData endpoints
- Azure PostgreSQL firewall
- Cosmos DB firewall
- Any other external services your automations call
