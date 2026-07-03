"""Async SQL Server integration — site mapping table queries.

Uses pymssql (pre-compiled wheels, no system ODBC driver required) wrapped in
asyncio.to_thread so the event loop is never blocked.

Connection config is read from Settings (SQLSERVER_* env vars). No credentials
are hardcoded.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pymssql

from backend.config import get_settings


def _query_sync(site_id: int) -> dict[str, Any] | None:
    """Synchronous SQL Server query — run via asyncio.to_thread.

    JOINs SubContractor.SiteMapping with SubContractor.TenantMapping
    (via SiteMapping.MappingId = TenantMapping.UniqueId) so that both the
    site mapping record and the correct Jicro tenant IDs are returned in one
    round-trip.
    """
    s = get_settings()
    site_table = s.sqlserver_mapping_table
    tenant_table = s.sqlserver_tenant_mapping_table
    with pymssql.connect(
        server=s.sqlserver_host,
        port=str(s.sqlserver_port),
        database=s.sqlserver_database,
        user=s.sqlserver_user,
        password=s.sqlserver_password,
        as_dict=True,
        login_timeout=30,
        timeout=30,
    ) as conn:
        with conn.cursor(as_dict=True) as cursor:
            cursor.execute(
                f"""
                SELECT
                    sm.UniqueId, sm.MappingId,
                    sm.MainContractorSiteId, sm.SubContractorSiteId,
                    sm.CreatedAt, sm.Deleted, sm.UpdatedAt, sm.Version,
                    tm.MainContractorTenantId, tm.SubContractorTenantId
                FROM {site_table} sm
                JOIN {tenant_table} tm
                    ON tm.UniqueId = sm.MappingId AND tm.Deleted = 0
                WHERE sm.Deleted = 0
                  AND (sm.MainContractorSiteId = %d OR sm.SubContractorSiteId = %d)
                """,
                (site_id, site_id),
            )
            return cursor.fetchone()


async def get_site_mapping(site_id: int) -> dict[str, Any] | None:
    """Query the mapping table for a given integer site ID (async, non-blocking).

    Returns the joined SiteMapping + TenantMapping row as a dict, enriched with:
      - 'matched_field': 'main' or 'sub' — which side site_id matched
      - 'jicro_tenant_id': the tenant GUID to use for the GetSiteByIdMsg call

    Returns None if no matching record exists.
    """
    row = await asyncio.to_thread(_query_sync, site_id)
    if row is None:
        return None

    matched_main = row["MainContractorSiteId"] == site_id
    row["matched_field"] = "main" if matched_main else "sub"
    row["jicro_tenant_id"] = str(
        row["MainContractorTenantId"] if matched_main else row["SubContractorTenantId"]
    )
    return row
