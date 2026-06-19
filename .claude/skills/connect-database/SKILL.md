---
name: connect-database
description: Set up a PostgreSQL database connection using asyncpg, create tables, and add CRUD operations. Use when an automation needs persistent storage.
argument-hint: <table/entity name>
---

# Connect to PostgreSQL Database

Set up database connectivity for: $ARGUMENTS

Each automation gets its **own database** on a shared Azure PostgreSQL server, named `automation-<name>`.

## Step 1: Configure Connection

Ensure `.env` has the `DATABASE_URL`:

```
DATABASE_URL=postgresql://<user>:<password>@<server>.postgres.database.azure.com:5432/automation-<name>?sslmode=require
```

## Step 2: Use the Database Module

The SDK provides `joblogic_sdk.db` with two async functions:

```python
from joblogic_sdk.db import query, execute

# SELECT — returns list of dicts
rows = await query("SELECT * FROM jobs WHERE tenant_id = $1", ("tenant-guid",))

# INSERT / UPDATE / DELETE — returns affected row count
affected = await execute("UPDATE jobs SET status = $1 WHERE id = $2", ("Done", 42))
```

Both use **asyncpg** for true async PostgreSQL access — no thread-pool wrapping needed.

## Step 3: Create Table

```python
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS <table_name> (
    id SERIAL PRIMARY KEY,
    -- Add columns here
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""

# Run at startup or in a setup script
await execute(CREATE_TABLE_SQL)
```

## Step 4: Add CRUD Routes

Create `backend/routes/<entity>.py` with endpoints:

- `POST /api/<entity>` — Create
- `GET /api/<entity>` — List
- `GET /api/<entity>/{id}` — Get by ID
- `PUT /api/<entity>/{id}` — Update
- `DELETE /api/<entity>/{id}` — Delete

Example:

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from joblogic_sdk.db import query, execute

router = APIRouter(prefix="/<entity>", tags=["<entity>"])


class CreateEntityRequest(BaseModel):
    name: str
    tenant_id: str


@router.post("/")
async def create_entity(req: CreateEntityRequest):
    row_count = await execute(
        "INSERT INTO <table_name> (name, tenant_id) VALUES ($1, $2)",
        (req.name, req.tenant_id),
    )
    return {"created": row_count}


@router.get("/")
async def list_entities(tenant_id: str):
    rows = await query(
        "SELECT * FROM <table_name> WHERE tenant_id = $1",
        (tenant_id,),
    )
    return rows


@router.get("/{entity_id}")
async def get_entity(entity_id: int):
    rows = await query(
        "SELECT * FROM <table_name> WHERE id = $1",
        (entity_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Not found")
    return rows[0]
```

## Guidelines

- Use **parameterized queries** (`$1, $2, $3` placeholders) — never concatenate SQL strings
- `asyncpg` is natively async — no need for `asyncio.to_thread()`
- Use `snake_case` for table and column names (PostgreSQL convention)
- Always include `created_at` and `updated_at` columns with `TIMESTAMPTZ`
- Database naming convention: `automation-<name>`
- Each automation gets its own database on the shared Azure PostgreSQL server
- Register new route files in `backend/main.py` with `app.include_router()`
