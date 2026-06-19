---
name: create-backend-automation
description: Create a webhook-based or timer-based backend automation. Use when building an automation triggered by a JobLogic webhook event or one that runs on a cron schedule.
argument-hint: <description of the automation and whether it is webhook or timer based>
---

# Create a Backend Automation

Build a backend automation for: $ARGUMENTS

Backend automations come in two flavours — **decide which one first**:

| Type        | Trigger                                                      | Example                                         |
| ----------- | ------------------------------------------------------------ | ----------------------------------------------- |
| **Webhook** | JobLogic fires a POST to your endpoint when an action occurs | "When a job is completed, sync invoice to Xero" |
| **Timer**   | APScheduler runs your function on a cron schedule            | "Every night at 2 AM, sync new clients"         |

Both types share the same project structure and run on the **backend** (port 8000).

---

## Common Steps (both types)

### Step 1: Discover the Jicro Message

Use the MCP tools to find the right Jicro message:

1. Call `search_endpoint` with a natural language query. Use `limit: 10`.
2. Review results and identify the correct message signature.
3. Call `get_endpoint` with the exact message name for the full payload schema.

### Step 2: Create Pydantic Models

Create `backend/routes/<automation_name>.py`:

```python
from pydantic import BaseModel

class MyAutomationRequest(BaseModel):
    tenant_id: str
    # Fields from the Jicro message payload schema …

class MyAutomationResponse(BaseModel):
    # Fields from the Jicro response shape …
```

### Step 3: Tenant ID

For backend automations the tenant ID is **single-tenant** — stored in the `.env` file as `TENANT_ID` and loaded via `joblogic_sdk.config`.

```python
from joblogic_sdk.config import get_settings

settings = get_settings()
tenant_id = settings.tenant_id
```

Never hardcode a tenant GUID.

---

## Webhook Automation

A webhook automation exposes a **POST endpoint** that JobLogic calls when a subscribed event occurs.

### Step W1: Create the Route Handler

```python
from fastapi import APIRouter, HTTPException
from joblogic_sdk.jicro import JicroClient, JicroError
from joblogic_sdk.notifications import slack_notification
from joblogic_sdk.audit import audit_log
from joblogic_sdk.models import ExecutionResult
from joblogic_sdk.config import get_settings

router = APIRouter(prefix="/automations/<name>", tags=["<name>"])

settings = get_settings()


@router.post("/webhook")
@slack_notification(automation_name="<Name>", automation_code="<CODE>")
@audit_log
async def handle_webhook(payload: MyWebhookPayload, tenant_id: str = settings.tenant_id):
    """Receives the webhook payload from JobLogic."""
    try:
        async with JicroClient() as client:
            result = await client.execute(
                tenant_id=tenant_id,
                service_name="<service>",
                message_signature="<MessageMsg>",
                payload=payload.model_dump(),
            )
            return result
    except JicroError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)
```

### Step W2: Register the Webhook in JobLogic

Webhook subscription is **manual**. After deploying, register the URL in the JobLogic admin panel:

```
POST https://<your-host>/api/automations/<name>/webhook
```

### Step W3: Register the Route in `backend/main.py`

```python
from backend.routes.<automation_name> import router as <name>_router
app.include_router(<name>_router, prefix="/api")
```

---

## Timer Automation

A timer automation runs a function on a **cron schedule** using APScheduler inside the FastAPI process.

### Step T1: Create the Processing Function

```python
from fastapi import APIRouter
from joblogic_sdk.jicro import JicroClient, JicroError
from joblogic_sdk.config import get_settings
from joblogic_sdk.notifications import slack_notification
from joblogic_sdk.audit import audit_log
from joblogic_sdk.models import ExecutionResult

router = APIRouter(prefix="/automations/<name>", tags=["<name>"])

settings = get_settings()


@slack_notification(automation_name="<Name>", automation_code="<CODE>")
@audit_log
async def run_scheduled_task(tenant_id: str = settings.tenant_id):
    """The actual work that runs on the cron schedule."""
    async with JicroClient() as client:
        result = await client.execute(
            tenant_id=tenant_id,
            service_name="<service>",
            message_signature="<MessageMsg>",
            payload={},
        )
    return ExecutionResult(
        execution_time="...",
        read_count=len(result.get("items", [])),
    )


@router.post("/trigger")
async def manual_trigger():
    """Allow manual triggering via API for testing."""
    return await run_scheduled_task()
```

### Step T2: Configure the Schedule

Add cron configuration to `.env`:

```
SCHEDULER_CRON_HOUR=2
SCHEDULER_CRON_MINUTE=0
```

### Step T3: Register the Scheduler in `backend/main.py`

```python
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app):
    # Import the processing function
    from backend.routes.<name> import run_scheduled_task

    scheduler.add_job(
        run_scheduled_task,
        CronTrigger(
            hour=int(os.getenv("SCHEDULER_CRON_HOUR", "2")),
            minute=int(os.getenv("SCHEDULER_CRON_MINUTE", "0")),
        ),
        id="<name>_scheduled",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
```

---

## Shared: Audit Logging

Add the `@audit_log` decorator from `joblogic_sdk.audit` to the processing function. This logs execution results to Cosmos DB (MongoDB API) via `AuditManager`.

For custom audit entries at intermediate steps:

```python
from joblogic_sdk.audit import AuditManager

await AuditManager.get_instance().log(
    automation_name="<automation_name>",
    automation_code="<CODE>",
    tenant_id=tenant_id,
    action="processing_complete",
    status="success",
    details={"result": result},
)
```

---

## Shared: Database (if needed)

If the automation needs persistent storage, see the **connect-database** skill. Each automation gets its own database on the shared Azure PostgreSQL server, named `automation-<name>`.

---

## Checklist

- [ ] Used MCP `search_endpoint` and `get_endpoint` to get Jicro docs
- [ ] Created Pydantic request/response models
- [ ] Route handler is `async`
- [ ] Used `JicroClient` (not ad-hoc HTTP calls)
- [ ] `tenant_id` loaded from env / config (not hardcoded)
- [ ] Error handling: `JicroError` → `HTTPException`
- [ ] Added notification decorator (`@slack_notification` or `@teams_notification`)
- [ ] Added `@audit_log` decorator from `joblogic_sdk.audit` for audit logging
- [ ] Registered route in `backend/main.py`
- [ ] (Timer only) APScheduler configured with cron from env vars
- [ ] Tested via Swagger UI at `http://localhost:8000/docs`
