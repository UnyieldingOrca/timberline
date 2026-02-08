"""Async HTTP client for the Loki API."""

from __future__ import annotations

import re
import time
from typing import Any

import httpx

_DURATION_RE = re.compile(r"^(\d+)\s*(s|m|h|d|w)$")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def _resolve_time(value: str | None) -> str | None:
    """Convert a relative duration string (e.g. '1h', '24h', '7d') to a
    nanosecond Unix epoch timestamp string.  RFC3339 and epoch values pass
    through unchanged.  Returns *None* when *value* is None/empty."""
    if not value:
        return None
    m = _DURATION_RE.match(value.strip())
    if m:
        seconds_ago = int(m.group(1)) * _UNIT_SECONDS[m.group(2)]
        ns = int((time.time() - seconds_ago) * 1e9)
        return str(ns)
    return value


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
        resolved_start = _resolve_time(start)
        resolved_end = _resolve_time(end)
        if resolved_start:
            params["start"] = resolved_start
        if resolved_end:
            params["end"] = resolved_end
        resp = await self._client.get("/loki/api/v1/query_range", params=params)
        resp.raise_for_status()
        return resp.json()

    async def labels(
        self, start: str | None = None, end: str | None = None
    ) -> list[str]:
        """List available label names."""
        params: dict[str, str] = {}
        resolved_start = _resolve_time(start)
        resolved_end = _resolve_time(end)
        if resolved_start:
            params["start"] = resolved_start
        if resolved_end:
            params["end"] = resolved_end
        resp = await self._client.get("/loki/api/v1/labels", params=params)
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def label_values(
        self, name: str, start: str | None = None, end: str | None = None
    ) -> list[str]:
        """Get values for a specific label."""
        params: dict[str, str] = {}
        resolved_start = _resolve_time(start)
        resolved_end = _resolve_time(end)
        if resolved_start:
            params["start"] = resolved_start
        if resolved_end:
            params["end"] = resolved_end
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
        resolved_start = _resolve_time(start)
        resolved_end = _resolve_time(end)
        if resolved_start:
            params["start"] = resolved_start
        if resolved_end:
            params["end"] = resolved_end
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
        resolved_start = _resolve_time(start)
        resolved_end = _resolve_time(end)
        if resolved_start:
            params["start"] = resolved_start
        if resolved_end:
            params["end"] = resolved_end
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
        resolved_start = _resolve_time(start)
        resolved_end = _resolve_time(end)
        if resolved_start:
            params["start"] = resolved_start
        if resolved_end:
            params["end"] = resolved_end
        resp = await self._client.get("/loki/api/v1/index/stats", params=params)
        resp.raise_for_status()
        return resp.json()
