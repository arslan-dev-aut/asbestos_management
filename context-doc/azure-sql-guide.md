# PostgreSQL Database Guide

## Overview

Each automation can optionally use an Azure Database for PostgreSQL. A shared PostgreSQL server is deployed and **each automation gets its own database**, named `automation-<name>`.

## Connection

Use **asyncpg** (native async PostgreSQL driver). The connection string is stored in the `DATABASE_URL` environment variable.

### Connection String Format

```
postgresql://<user>:<password>@<server>.postgres.database.azure.com:5432/automation-<name>?sslmode=require
```

## Usage Pattern (asyncpg — async)

The SDK provides `joblogic_sdk.db` with ready-to-use async functions:

```python
from joblogic_sdk.db import query, execute

# SELECT — returns a list of dicts
rows = await query("SELECT * FROM jobs WHERE tenant_id = $1", ("tenant-guid",))

# INSERT / UPDATE / DELETE — returns affected row count
affected = await execute("UPDATE jobs SET status = $1 WHERE id = $2", ("Done", 42))
```

### How `joblogic_sdk.db` works

```python
import asyncpg

from joblogic_sdk.config import get_settings


def _dsn() -> str:
    dsn = get_settings().database_url
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set")
    return dsn


async def query(sql: str, params: tuple = ()) -> list[dict]:
    conn = await asyncpg.connect(_dsn())
    try:
        rows = await conn.fetch(sql, *params)
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def execute(sql: str, params: tuple = ()) -> int:
    conn = await asyncpg.connect(_dsn())
    try:
        result = await conn.execute(sql, *params)
        parts = result.split()
        return int(parts[-1])
    finally:
        await conn.close()
```

`asyncpg` is **natively async** — no `asyncio.to_thread()` wrapping needed.

## Parameter Syntax

PostgreSQL uses **numbered placeholders**: `$1`, `$2`, `$3`, etc.

```python
# Single parameter
rows = await query("SELECT * FROM jobs WHERE status = $1", ("active",))

# Multiple parameters
rows = await query(
    "SELECT * FROM jobs WHERE status = $1 AND tenant_id = $2",
    ("active", "tenant-guid"),
)
```

## Database Naming Convention

- Each automation gets its own database: `automation-<name>`
- Tables use `snake_case`: `job_record`, `sync_log`
- Columns use `snake_case`: `tenant_id`, `created_at`

## PostgreSQL Data Types

| Use case | PostgreSQL type |
|----------|----------------|
| Auto-increment ID | `SERIAL` or `BIGSERIAL` |
| UUID | `UUID` (with `gen_random_uuid()` default) |
| Text | `TEXT` or `VARCHAR(n)` |
| Integer | `INTEGER`, `BIGINT` |
| Boolean | `BOOLEAN` |
| Timestamp | `TIMESTAMPTZ` (always use timezone-aware) |
| JSON | `JSONB` (binary JSON, indexable) |
| Decimal | `NUMERIC(p, s)` |

## Creating Tables

```python
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS job_record (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""

await execute(CREATE_TABLE_SQL)
```

## When to Use a Database

| Scenario | Use database? |
|----------|--------------|
| Simple pass-through to Jicro | No |
| Need to cache/store intermediate data | Yes |
| Need audit logging beyond Joblogic | Yes (also consider MongoDB) |
| Scheduling or queue management | Yes |
| Need to join data from multiple Jicro calls | Consider it |
