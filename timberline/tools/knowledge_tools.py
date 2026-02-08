"""Knowledge base tools for agent use."""

from __future__ import annotations

import json
from typing import Any, Callable

from loguru import logger

from timberline.knowledge.store import KnowledgeStore


def build_knowledge_tools(store: KnowledgeStore) -> list[Callable[..., Any]]:
    """Build list of knowledge base tool functions with the store bound via closures."""

    async def read_knowledge(path: str) -> str:
        """Read a file from the knowledge base. Returns the file contents.

        Args:
            path: Relative path within the knowledge base, e.g. 'findings/2026-02-07.md'.
        """
        logger.info(f"read_knowledge: path={path!r}")
        try:
            content = store.read(path)
            logger.info(f"read_knowledge: returned {len(content)} chars")
            return content
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"read_knowledge: {e}")
            return f"Error: {e}"

    async def write_knowledge(path: str, content: str, append: bool = False) -> str:
        """Write or append to a file in the knowledge base. Creates parent directories as needed.

        Args:
            path: Relative path within the knowledge base.
            content: Content to write.
            append: If true, append instead of overwrite (default false).
        """
        action = "append" if append else "write"
        logger.info(f"write_knowledge: {action} path={path!r} ({len(content)} chars)")
        try:
            store.write(path, content, append=append)
            label = "Appended to" if append else "Wrote"
            logger.info(f"write_knowledge: done")
            return f"{label} {path}"
        except ValueError as e:
            logger.error(f"write_knowledge: {e}")
            return f"Error: {e}"

    async def list_knowledge(directory: str = ".", pattern: str = "*") -> str:
        """List files in the knowledge base. Supports glob patterns for filtering.

        Args:
            directory: Directory to list (default: root).
            pattern: Glob pattern filter (default: '*').
        """
        logger.info(f"list_knowledge: directory={directory!r} pattern={pattern!r}")
        try:
            files = store.list_files(directory=directory, pattern=pattern)
            logger.info(f"list_knowledge: found {len(files)} files")
            if not files:
                return "No files found."
            return "\n".join(files)
        except ValueError as e:
            logger.error(f"list_knowledge: {e}")
            return f"Error: {e}"

    async def search_knowledge(text: str, directory: str = ".") -> str:
        """Search for a string across all files in the knowledge base. Case-insensitive.

        Args:
            text: Text to search for.
            directory: Directory to search in (default: root).
        """
        logger.info(f"search_knowledge: text={text!r} directory={directory!r}")
        try:
            matches = store.search(text=text, directory=directory)
            logger.info(f"search_knowledge: found {len(matches)} matches")
            if not matches:
                return "No matches found."
            return json.dumps(matches, indent=2)
        except ValueError as e:
            logger.error(f"search_knowledge: {e}")
            return f"Error: {e}"

    return [read_knowledge, write_knowledge, list_knowledge, search_knowledge]
