"""Async HTTP client for the Loki API."""

from __future__ import annotations

from typing import Any

import httpx


class LokiClient:
    """Wraps the Loki HTTP API with an async httpx client."""

    def __init__(self, base_url: str = "http://localhost:3100", org_id: str | None = None) -> None:
        headers: dict[str, str] = {}
        if org_id:
            headers["X-Scope-OrgID"] = org_id
        self._client = httpx.AsyncClient(base_url=base_url, headers=headers, timeout=30.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> LokiClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # -- Loki endpoints --

    async def ready(self) -> bool:
        """Check if Loki is ready."""
        resp = await self._client.get("/ready")
        return resp.status_code == 200

    async def query_range(
        self,
        query: str,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
        direction: str = "backward",
    ) -> dict[str, Any]:
        """Execute a LogQL query_range request."""
        params: dict[str, Any] = {"query": query, "limit": limit, "direction": direction}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        resp = await self._client.get("/loki/api/v1/query_range", params=params)
        resp.raise_for_status()
        return resp.json()

    async def labels(
        self, start: str | None = None, end: str | None = None
    ) -> list[str]:
        """List available label names."""
        params: dict[str, str] = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        resp = await self._client.get("/loki/api/v1/labels", params=params)
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def label_values(
        self, name: str, start: str | None = None, end: str | None = None
    ) -> list[str]:
        """Get values for a specific label."""
        params: dict[str, str] = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        resp = await self._client.get(f"/loki/api/v1/label/{name}/values", params=params)
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def series(
        self,
        match: list[str],
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, str]]:
        """Find active log streams matching selectors."""
        params: dict[str, Any] = {"match[]": match}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        resp = await self._client.get("/loki/api/v1/series", params=params)
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def volume_range(
        self,
        query: str,
        start: str | None = None,
        end: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Get volume statistics over time for matching streams."""
        params: dict[str, Any] = {"query": query, "limit": limit}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        resp = await self._client.get("/loki/api/v1/index/volume_range", params=params)
        resp.raise_for_status()
        return resp.json()

    async def stats(
        self,
        query: str,
        start: str | None = None,
        end: str | None = None,
    ) -> dict[str, Any]:
        """Get index-level statistics (stream count, bytes, entries)."""
        params: dict[str, Any] = {"query": query}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        resp = await self._client.get("/loki/api/v1/index/stats", params=params)
        resp.raise_for_status()
        return resp.json()
