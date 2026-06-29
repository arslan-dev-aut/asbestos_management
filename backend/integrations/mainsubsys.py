"""MainSubSys integration — name and ID resolution via JicroClient only.

Entity resolution strategy (per SDK/CLAUDE.md conventions):
- All lookups use JicroClient (exec-jicro).  OData is not used.
  Customers → GetCustomerMsg / GetFilteredCustomerMsg
  Sites     → GetSiteMsg / SearchSiteMsg
  Assets    → GetAssetByUniqueIdMsg / GetFilteredAssetMsg
  Users     → GetUserByGuidMsg

Auth is configured via the SDK's own env vars:
  JICRO_BASE_URL      — environment-specific MainSubSys automation API URL
  JICRO_AUTH_TOKEN    — jl-x-header-token-key value for that environment
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from joblogic_sdk.jicro import JicroClient, JicroError

from backend.database.exceptions import UpstreamError


@dataclass
class ResolvedNames:
    """Bag of id → name maps resolved for one response build."""

    customers: dict[str, str] = field(default_factory=dict)
    sites:     dict[str, str] = field(default_factory=dict)
    assets:    dict[str, str] = field(default_factory=dict)
    users:     dict[str, str] = field(default_factory=dict)

    def customer(self, cid: str | None) -> str | None:
        return self.customers.get(str(cid)) if cid else None

    def site(self, sid: str | None) -> str | None:
        return self.sites.get(str(sid)) if sid else None

    def asset(self, aid: str | None) -> str | None:
        return self.assets.get(str(aid)) if aid else None

    def user(self, uid: str | None) -> str | None:
        return self.users.get(str(uid)) if uid else None


class MainSubSysClient:
    """Async context-manager client.  Usage::

        async with MainSubSysClient(tenant_id) as mss:
            names = await mss.resolve_users(user_ids)
    """

    def __init__(self, tenant_id: str) -> None:
        self._tenant_id = tenant_id

    async def __aenter__(self) -> MainSubSysClient:
        return self

    async def __aexit__(self, *_exc) -> None:
        pass

    # ------------------------------------------------------------------ #
    # Single-entity fetchers (GUID → name)
    # ------------------------------------------------------------------ #

    async def _fetch_customer_name(self, customer_id: str) -> tuple[str, str | None]:
        try:
            async with JicroClient() as client:
                result = await client.execute(
                    tenant_id=self._tenant_id,
                    service_name="core",
                    message_signature="GetCustomerMsg",
                    payload={"UniqueId": customer_id},
                )
            obj = (result or {}).get("jicroResponse") or {}
            name = obj.get("Name") or obj.get("name")
            return customer_id, str(name) if name else None
        except JicroError:
            return customer_id, None

    async def _fetch_site_name(self, site_id: str) -> tuple[str, str | None]:
        try:
            async with JicroClient() as client:
                result = await client.execute(
                    tenant_id=self._tenant_id,
                    service_name="core",
                    message_signature="GetSiteMsg",
                    payload={"UniqueId": site_id},
                )
            obj = (result or {}).get("jicroResponse") or {}
            name = obj.get("Name") or obj.get("name")
            return site_id, str(name) if name else None
        except JicroError:
            return site_id, None

    async def _fetch_asset_name(self, asset_id: str) -> tuple[str, str | None]:
        try:
            async with JicroClient() as client:
                result = await client.execute(
                    tenant_id=self._tenant_id,
                    service_name="core",
                    message_signature="GetAssetByUniqueIdMsg",
                    payload={"UniqueId": asset_id},
                )
            obj = (result or {}).get("jicroResponse") or {}
            name = obj.get("Description") or obj.get("description")
            return asset_id, str(name) if name else None
        except JicroError:
            return asset_id, None

    async def _fetch_user_name(self, user_id: str) -> tuple[str, str | None]:
        try:
            async with JicroClient() as client:
                result = await client.execute(
                    tenant_id=self._tenant_id,
                    service_name="role",
                    message_signature="GetUserByGuidMsg",
                    payload={"Guid": user_id},
                )
            user = (result or {}).get("jicroResponse") or {}
            name = user.get("name")
            return user_id, str(name) if name else None
        except JicroError:
            return user_id, None

    # ------------------------------------------------------------------ #
    # Public resolution API
    # ------------------------------------------------------------------ #

    async def resolve_customers(self, ids: set[str]) -> dict[str, str]:
        ids = {str(i) for i in ids if i}
        if not ids:
            return {}
        pairs = await asyncio.gather(*(self._fetch_customer_name(cid) for cid in ids))
        return {cid: name for cid, name in pairs if name is not None}

    async def resolve_sites(self, ids: set[str]) -> dict[str, str]:
        ids = {str(i) for i in ids if i}
        if not ids:
            return {}
        pairs = await asyncio.gather(*(self._fetch_site_name(sid) for sid in ids))
        return {sid: name for sid, name in pairs if name is not None}

    async def resolve_assets(self, ids: set[str]) -> dict[str, str]:
        ids = {str(i) for i in ids if i}
        if not ids:
            return {}
        pairs = await asyncio.gather(*(self._fetch_asset_name(aid) for aid in ids))
        return {aid: name for aid, name in pairs if name is not None}

    async def resolve_users(self, ids: set[str]) -> dict[str, str]:
        """Resolve a set of user GUIDs to display names in parallel."""
        ids = {str(i) for i in ids if i}
        if not ids:
            return {}
        pairs = await asyncio.gather(*(self._fetch_user_name(uid) for uid in ids))
        return {uid: name for uid, name in pairs if name is not None}

    async def validate_assets(self, ids: set[str]) -> set[str]:
        """Return the subset of asset IDs that still exist in MainSubSys."""
        found = await self.resolve_assets(ids)
        return set(found.keys())

    async def resolve_all(
        self,
        *,
        customer_ids: set[str] | None = None,
        site_ids:     set[str] | None = None,
        asset_ids:    set[str] | None = None,
        user_ids:     set[str] | None = None,
    ) -> ResolvedNames:
        """Resolve every needed name map concurrently."""
        customers, sites, assets, users = await asyncio.gather(
            self.resolve_customers(customer_ids or set()),
            self.resolve_sites    (site_ids     or set()),
            self.resolve_assets   (asset_ids    or set()),
            self.resolve_users    (user_ids     or set()),
        )
        return ResolvedNames(customers=customers, sites=sites, assets=assets, users=users)

    # ------------------------------------------------------------------ #
    # Search helpers (text → list of UniqueId GUIDs)
    # ------------------------------------------------------------------ #

    async def search_customer_ids(self, text: str) -> list[str]:
        """Return customer UniqueId GUIDs whose name contains *text*."""
        try:
            async with JicroClient() as client:
                result = await client.execute(
                    tenant_id=self._tenant_id,
                    service_name="core",
                    message_signature="GetFilteredCustomerMsg",
                    payload={
                        "SearchTerm": text,
                        "IncludeInactive": False,
                        "PageIndex": 1,
                        "PageSize": 200,
                    },
                )
        except JicroError as exc:
            raise UpstreamError("MainSubSys is unavailable.", detail=str(exc)) from exc
        jicro = (result or {}).get("jicroResponse") or {}
        customers = jicro.get("customers") or []
        return [str(c["uniqueId"]) for c in customers if c.get("uniqueId")]

    async def search_site_ids(self, text: str) -> list[str]:
        """Return site UniqueId GUIDs whose name contains *text*."""
        try:
            async with JicroClient() as client:
                result = await client.execute(
                    tenant_id=self._tenant_id,
                    service_name="core",
                    message_signature="SearchSiteMsg",
                    payload={
                        "SearchTerm": text,
                        "PageSize": 200,
                        "PageIndex": 1,
                        "SelectedTab": 3,
                    },
                )
        except JicroError as exc:
            raise UpstreamError("MainSubSys is unavailable.", detail=str(exc)) from exc
        jicro = (result or {}).get("jicroResponse") or {}
        sites = jicro.get("sites") or []
        return [str(s["uniqueId"]) for s in sites if s.get("uniqueId")]

    # ------------------------------------------------------------------ #
    # Exact-name lookup (used by bulk upload row validation)
    # ------------------------------------------------------------------ #

    async def find_customer_by_name(self, name: str) -> str | None:
        """Return the UniqueId GUID of the customer with exactly this name."""
        try:
            async with JicroClient() as client:
                result = await client.execute(
                    tenant_id=self._tenant_id,
                    service_name="core",
                    message_signature="GetFilteredCustomerMsg",
                    payload={
                        "SearchTerm": name.strip(),
                        "IncludeInactive": False,
                        "PageIndex": 1,
                        "PageSize": 50,
                    },
                )
        except JicroError as exc:
            raise UpstreamError("MainSubSys is unavailable.", detail=str(exc)) from exc
        jicro = (result or {}).get("jicroResponse") or {}
        needle = name.strip().lower()
        for c in jicro.get("customers") or []:
            if (c.get("name") or "").lower() == needle and c.get("uniqueId"):
                return str(c["uniqueId"])
        return None

    async def find_site_by_name(self, name: str) -> str | None:
        """Return the UniqueId GUID of the site with exactly this name."""
        try:
            async with JicroClient() as client:
                result = await client.execute(
                    tenant_id=self._tenant_id,
                    service_name="core",
                    message_signature="SearchSiteMsg",
                    payload={
                        "SearchTerm": name.strip(),
                        "PageSize": 50,
                        "PageIndex": 1,
                        "SelectedTab": 3,
                    },
                )
        except JicroError as exc:
            raise UpstreamError("MainSubSys is unavailable.", detail=str(exc)) from exc
        jicro = (result or {}).get("jicroResponse") or {}
        needle = name.strip().lower()
        for s in jicro.get("sites") or []:
            if (s.get("name") or "").lower() == needle and s.get("uniqueId"):
                return str(s["uniqueId"])
        return None

    async def find_asset_by_name(self, name: str) -> str | None:
        """Return the UniqueId GUID of the asset with exactly this description."""
        try:
            async with JicroClient() as client:
                result = await client.execute(
                    tenant_id=self._tenant_id,
                    service_name="core",
                    message_signature="GetFilteredAssetMsg",
                    payload={
                        "SearchTerm": name.strip(),
                        "SearchCondition": 0,
                        "IncludeInactive": False,
                        "OrderBy": 0,
                        "PageIndex": 1,
                        "PageSize": 50,
                    },
                )
        except JicroError as exc:
            raise UpstreamError("MainSubSys is unavailable.", detail=str(exc)) from exc
        jicro = (result or {}).get("jicroResponse") or {}
        assets = jicro.get("Assets") or jicro.get("assets") or []
        needle = name.strip().lower()
        for a in assets:
            desc = a.get("Description") or a.get("description") or ""
            uid = a.get("UniqueId") or a.get("uniqueId")
            if desc.lower() == needle and uid:
                return str(uid)
        return None

    # ------------------------------------------------------------------ #
    # UUID → integer auto-ID resolvers
    # ------------------------------------------------------------------ #

    async def get_customer_auto_id(self, unique_id: str) -> int:
        """Resolve a customer UniqueId (GUID) to its integer auto-ID.

        Raises ``NotFoundError`` if no matching customer exists in the tenancy.
        """
        from backend.database.exceptions import NotFoundError

        try:
            async with JicroClient() as client:
                result = await client.execute(
                    tenant_id=self._tenant_id,
                    service_name="core",
                    message_signature="GetCustomerMsg",
                    payload={"UniqueId": unique_id},
                )
        except JicroError as exc:
            raise UpstreamError("MainSubSys is unavailable.", detail=str(exc)) from exc
        obj = (result or {}).get("jicroResponse") or {}
        auto_id = obj.get("Id") or obj.get("id")
        if not auto_id:
            raise NotFoundError(f"Customer '{unique_id}' not found.")
        return int(auto_id)

    async def get_site_auto_id(self, unique_id: str) -> int:
        """Resolve a site UniqueId (GUID) to its integer auto-ID.

        Raises ``NotFoundError`` if no matching site exists in the tenancy.
        """
        from backend.database.exceptions import NotFoundError

        try:
            async with JicroClient() as client:
                result = await client.execute(
                    tenant_id=self._tenant_id,
                    service_name="core",
                    message_signature="GetSiteMsg",
                    payload={"UniqueId": unique_id},
                )
        except JicroError as exc:
            raise UpstreamError("MainSubSys is unavailable.", detail=str(exc)) from exc
        obj = (result or {}).get("jicroResponse") or {}
        auto_id = obj.get("Id") or obj.get("id")
        if not auto_id:
            raise NotFoundError(f"Site '{unique_id}' not found.")
        return int(auto_id)

    # ------------------------------------------------------------------ #
    # Customer / site listing (for lookup dropdowns)
    # ------------------------------------------------------------------ #

    async def list_customers(
        self, search: str | None = None, page_size: int = 20
    ) -> list[dict]:
        """List customers via GetFilteredCustomerMsg."""
        try:
            async with JicroClient() as client:
                result = await client.execute(
                    tenant_id=self._tenant_id,
                    service_name="core",
                    message_signature="GetFilteredCustomerMsg",
                    payload={
                        "SearchTerm": search or "",
                        "IncludeInactive": False,
                        "PageIndex": 1,
                        "PageSize": page_size,
                    },
                )
        except JicroError as exc:
            raise UpstreamError("MainSubSys is unavailable.", detail=str(exc)) from exc
        jicro = (result or {}).get("jicroResponse") or {}
        return jicro.get("customers") or []

    async def list_sites_for_customer(
        self, customer_unique_id: str, search: str | None = None, page_size: int = 500
    ) -> list[dict]:
        """List sites for a customer via SearchSiteMsg, scoped by customer UniqueId (GUID).

        Resolves the UUID to the integer auto-ID required by SearchSiteMsg first.
        """
        customer_auto_id = await self.get_customer_auto_id(customer_unique_id)
        try:
            async with JicroClient() as client:
                result = await client.execute(
                    tenant_id=self._tenant_id,
                    service_name="core",
                    message_signature="SearchSiteMsg",
                    payload={
                        "SearchTerm": search or "",
                        "CustomerId": customer_auto_id,
                        "PageSize": page_size,
                        "PageIndex": 1,
                        "SelectedTab": 3,
                    },
                )
        except JicroError as exc:
            raise UpstreamError("MainSubSys is unavailable.", detail=str(exc)) from exc
        jicro = (result or {}).get("jicroResponse") or {}
        return jicro.get("Sites") or jicro.get("sites") or []

    async def list_assets_for_site(
        self, site_unique_id: str, search: str | None = None, page_size: int = 500
    ) -> list[dict]:
        """List assets for a site via GetFilteredAssetMsg, scoped by site UniqueId (GUID).

        Resolves the UUID to the integer auto-ID required by GetFilteredAssetMsg first.
        """
        site_auto_id = await self.get_site_auto_id(site_unique_id)
        try:
            async with JicroClient() as client:
                result = await client.execute(
                    tenant_id=self._tenant_id,
                    service_name="core",
                    message_signature="GetFilteredAssetMsg",
                    payload={
                        "SiteId": site_auto_id,
                        "SearchTerm": search or "",
                        "SearchCondition": 0,
                        "IncludeInactive": False,
                        "OrderBy": 0,
                        "PageIndex": 1,
                        "PageSize": page_size,
                    },
                )
        except JicroError as exc:
            raise UpstreamError("MainSubSys is unavailable.", detail=str(exc)) from exc
        jicro = (result or {}).get("jicroResponse") or {}
        return jicro.get("Assets") or jicro.get("assets") or []
