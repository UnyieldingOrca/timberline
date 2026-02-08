"""Knowledge base tools for agent use."""

from __future__ import annotations

import json
from typing import Any, Callable

from timberline.knowledge.store import KnowledgeStore


def build_knowledge_tools(store: KnowledgeStore) -> list[Callable[..., Any]]:
    """Build list of knowledge base tool functions with the store bound via closures."""

    async def read_knowledge(path: str) -> str:
        """Read a file from the knowledge base. Returns the file contents.

        Args:
            path: Relative path within the knowledge base, e.g. 'findings/2026-02-07.md'.
        """
        return store.read(path)

    async def write_knowledge(path: str, content: str, append: bool = False) -> str:
        """Write or append to a file in the knowledge base. Creates parent directories as needed.

        Args:
            path: Relative path within the knowledge base.
            content: Content to write.
            append: If true, append instead of overwrite (default false).
        """
        store.write(path, content, append=append)
        action = "Appended to" if append else "Wrote"
        return f"{action} {path}"

    async def list_knowledge(directory: str = ".", pattern: str = "*") -> str:
        """List files in the knowledge base. Supports glob patterns for filtering.

        Args:
            directory: Directory to list (default: root).
            pattern: Glob pattern filter (default: '*').
        """
        files = store.list_files(directory=directory, pattern=pattern)
        if not files:
            return "No files found."
        return "\n".join(files)

    async def search_knowledge(text: str, directory: str = ".") -> str:
        """Search for a string across all files in the knowledge base. Case-insensitive.

        Args:
            text: Text to search for.
            directory: Directory to search in (default: root).
        """
        matches = store.search(text=text, directory=directory)
        if not matches:
            return "No matches found."
        return json.dumps(matches, indent=2)

    return [read_knowledge, write_knowledge, list_knowledge, search_knowledge]
