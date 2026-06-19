---
name: audit-logs
description: Add Slack/Teams notifications and Cosmos DB (MongoDB API) audit logging to an automation. Use when you need execution monitoring, failure alerting, or persistent audit trails.
argument-hint: <automation name to add audit logging to>
---

# Audit Logging & Notifications

Add audit logging and notifications to: $ARGUMENTS

This skill covers two capabilities:

1. **Notifications** — Slack and Teams alerts on automation success / failure
2. **Audit logging** — Persistent execution logs in Cosmos DB (MongoDB API) via `AuditManager`

---

## Notifications

Pre-built decorators are available in `joblogic_sdk.notifications`. They wrap async processing functions and automatically send alerts based on the outcome.

**Note:** Notification decorators no longer auto-log to audit. Add the `@audit_log` decorator from `joblogic_sdk.audit` when audit logging is needed.

### Slack Notification

```python
from joblogic_sdk.notifications import slack_notification
from joblogic_sdk.audit import audit_log
from joblogic_sdk.models import ExecutionResult


@slack_notification(
    automation_name="My Automation",
    automation_code="MY-AUTO",
)
@audit_log
async def process(tenant_id: str) -> ExecutionResult:
    # Your automation logic here …
    return ExecutionResult(
        execution_time="2024-01-01T12:00:00Z",
        read_count=10,
        create_count=5,
        update_count=2,
    )
```

**Alert types:**
| Scenario | Alert Type | Webhook Used |
|----------|-----------|--------------|
| All operations succeed (`failure_count == 0`) | Success (1) | `SLACK_SUCCESS_WEBHOOK` |
| Some operations failed (`failure_count > 0`) | Partial Failure (2) | `SLACK_PARTIAL_FAILURE_WEBHOOK` |
| Function raises an exception | Complete Failure (3) | `SLACK_FAILURE_WEBHOOK` |

### Teams Notification

```python
from joblogic_sdk.notifications import teams_notification
from joblogic_sdk.audit import audit_log
from joblogic_sdk.models import ExecutionResult


@teams_notification(
    automation_name="My Automation",
    automation_code="MY-AUTO",
)
@audit_log
async def process(tenant_id: str) -> ExecutionResult:
    # Your automation logic here …
    return ExecutionResult(
        execution_time="2024-01-01T12:00:00Z",
        read_count=10,
        create_count=5,
    )
```

Teams notifications post to a single **Workflow webhook URL** with an `is_success` flag.

### Combining Both

You can stack notification and audit decorators:

```python
@slack_notification(automation_name="My Auto", automation_code="MY-AUTO")
@teams_notification(automation_name="My Auto", automation_code="MY-AUTO")
@audit_log
async def process(tenant_id: str) -> ExecutionResult:
    ...
```

### Tenant ID Parameter

By default, the decorators look for a keyword argument named `tenant_id` in the wrapped function. If your function uses a different parameter name, specify it:

```python
@slack_notification(
    automation_name="My Auto",
    automation_code="MY-AUTO",
    tenant_id_param="my_tenant",
)
@audit_log
async def process(my_tenant: str) -> ExecutionResult:
    ...
```

### Required Environment Variables

```env
# Slack
SLACK_ENABLED=true
SLACK_SUCCESS_WEBHOOK=https://hooks.slack.com/services/...
SLACK_FAILURE_WEBHOOK=https://hooks.slack.com/services/...
SLACK_PARTIAL_FAILURE_WEBHOOK=https://hooks.slack.com/services/...

# Teams
TEAMS_ENABLED=1
TEAMS_WORKFLOW_URL=https://prod-XX.westeurope.logic.azure.com/...

# Common
APPLICATION_ENVIRONMENT=development
```

---

## ExecutionResult Model

All notification decorators expect the wrapped function to return an `ExecutionResult`:

```python
from joblogic_sdk.models import ExecutionResult

result = ExecutionResult(
    execution_time="2024-01-01T12:00:00Z",  # ISO-8601 or duration string
    read_count=10,
    create_count=5,
    update_count=2,
    delete_count=0,
    failure_count=0,
    no_op_count=3,
    custom_message="Optional context about the run",
    azure_blob_storage="https://storage.blob.core.windows.net/logs/...",
)
```

Fields:
| Field | Type | Description |
|-------|------|-------------|
| `execution_time` | `str` | Timestamp or duration |
| `read_count` | `int` | Records read |
| `create_count` | `int` | Records created |
| `update_count` | `int` | Records updated |
| `delete_count` | `int` | Records deleted |
| `failure_count` | `int` | Failed operations (triggers partial-failure alert if > 0) |
| `no_op_count` | `int` | Records skipped |
| `custom_message` | `str` | Free-text context |
| `azure_blob_storage` | `str \| None` | Link to detailed log blob |

---

## Cosmos DB (MongoDB API) Audit Logging

Audit logs are stored in **Cosmos DB (MongoDB API)** via `AuditManager`, using the `motor` async driver.

### Automatic Logging with Decorator

Add the `@audit_log` decorator from `joblogic_sdk.audit` to automatically log every execution. This decorator works alongside notification decorators but is applied separately.

```python
from joblogic_sdk.audit import audit_log

@audit_log
async def process(tenant_id: str) -> ExecutionResult:
    ...
```

### Manual Logging

For custom entries outside the `@audit_log` decorator:

```python
from joblogic_sdk.audit import AuditManager

await AuditManager.get_instance().log(
    automation_name="my_automation",
    automation_code="MY-AUTO",
    tenant_id=tenant_id,
    action="processing_started",
    status="success",
    details={"input_count": 50},
)
```

### Querying Audit Logs

REST endpoints:

- `GET /api/audit/logs` — List with filters (automation_name, tenant_id, status, from_date, to_date, page, page_size)
- `GET /api/audit/logs/{id}` — Single entry
- `GET /api/audit/stats` — Summary counts

### Required Environment Variables

```env
AUDIT_MONGODB_CONNECTION_STRING=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
AUDIT_DB_NAME=automation-audit
AUDIT_COLLECTION_NAME=audit_logs
```

---

## Typical Integration Pattern

Use notification decorators for alerts and `@audit_log` for audit logging:

```python
from joblogic_sdk.notifications import slack_notification
from joblogic_sdk.audit import audit_log
from joblogic_sdk.models import ExecutionResult


@slack_notification(automation_name="Invoice Sync", automation_code="INV-SYNC")
@audit_log
async def process_invoices(tenant_id: str) -> ExecutionResult:
    # … automation logic …

    return ExecutionResult(
        execution_time="2024-01-01T12:00:00Z",
        read_count=10,
        create_count=5,
    )
```

The decorators:

1. `@slack_notification` sends a Slack/Teams notification (if enabled)
2. `@audit_log` writes an audit log entry to Cosmos DB with all `ExecutionResult` counters

For additional custom audit entries at intermediate steps:

```python
from joblogic_sdk.audit import AuditManager

await AuditManager.get_instance().log(
    automation_name="invoice_sync",
    automation_code="INV-SYNC",
    tenant_id=tenant_id,
    action="batch_started",
    status="success",
    details={"batch_size": 50},
)
```

---

## Checklist

- [ ] Notification decorator added to the processing function
- [ ] `@audit_log` decorator added for audit logging
- [ ] `ExecutionResult` returned with accurate counts
- [ ] Slack/Teams webhook env vars configured in `.env`
- [ ] `SLACK_ENABLED` / `TEAMS_ENABLED` set appropriately
- [ ] `APPLICATION_ENVIRONMENT` set (e.g., `development`, `staging`, `production`)
- [ ] `AUDIT_MONGODB_CONNECTION_STRING`, `AUDIT_DB_NAME`, `AUDIT_COLLECTION_NAME` configured in `.env`
- [ ] Custom `AuditManager.get_instance().log(...)` calls added at key intermediate steps (optional)
