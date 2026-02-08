"""Loki tools for agent use."""

from __future__ import annotations

import json
from typing import Any, Callable

from timberline.loki.client import LokiClient


def build_loki_tools(client: LokiClient) -> list[Callable[..., Any]]:
    """Build list of Loki tool functions with the client bound via closures."""

    async def query_logs(
        query: str,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
        direction: str = "backward",
    ) -> str:
        """Execute a LogQL query against Loki. Returns matching log entries with timestamps and labels.

        Args:
            query: LogQL query string, e.g. '{app="nginx"} |= "error"'.
            start: Start time (RFC3339 or relative like '1h').
            end: End time (RFC3339 or relative).
            limit: Max entries to return (default 100).
            direction: 'forward' or 'backward' (default 'backward').
        """
        result = await client.query_range(
            query=query, start=start, end=end, limit=limit, direction=direction
        )
        return json.dumps(result, indent=2)

    async def get_labels(
        start: str | None = None,
        end: str | None = None,
    ) -> str:
        """List all available label names in Loki. Use this to discover what labels exist for filtering.

        Args:
            start: Start time filter.
            end: End time filter.
        """
        labels = await client.labels(start=start, end=end)
        return json.dumps(labels, indent=2)

    async def get_label_values(
        label: str,
        start: str | None = None,
        end: str | None = None,
    ) -> str:
        """Get all values for a specific label. Useful for discovering namespaces, apps, pods, etc.

        Args:
            label: Label name to get values for.
            start: Start time filter.
            end: End time filter.
        """
        values = await client.label_values(name=label, start=start, end=end)
        return json.dumps(values, indent=2)

    async def get_series(
        match: list[str],
        start: str | None = None,
        end: str | None = None,
    ) -> str:
        """Find active log streams matching label selectors. Returns all label sets for matching streams.

        Args:
            match: Label matchers, e.g. ['{app="nginx"}'].
            start: Start time filter.
            end: End time filter.
        """
        series = await client.series(match=match, start=start, end=end)
        return json.dumps(series, indent=2)

    async def get_log_volume(
        query: str,
        start: str | None = None,
        end: str | None = None,
        limit: int = 10,
    ) -> str:
        """Get volume statistics (bytes and entries over time) for matching streams. Useful for spotting spikes.

        Args:
            query: LogQL stream selector, e.g. '{namespace="prod"}'.
            start: Start time.
            end: End time.
            limit: Max series to return (default 10).
        """
        volume = await client.volume_range(query=query, start=start, end=end, limit=limit)
        return json.dumps(volume, indent=2)

    async def get_log_stats(
        query: str,
        start: str | None = None,
        end: str | None = None,
    ) -> str:
        """Get index-level statistics: total stream count, bytes, and entries for matching streams.

        Args:
            query: LogQL stream selector.
            start: Start time.
            end: End time.
        """
        stats = await client.stats(query=query, start=start, end=end)
        return json.dumps(stats, indent=2)

    return [query_logs, get_labels, get_label_values, get_series, get_log_volume, get_log_stats]
