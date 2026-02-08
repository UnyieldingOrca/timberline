"""Filesystem-based knowledge store with path traversal protection."""

from __future__ import annotations

import fnmatch
from pathlib import Path


class KnowledgeStore:
    """Manages a filesystem directory where the agent stores what it learns."""

    def __init__(self, base_path: Path) -> None:
        self._base = base_path.resolve()

    @property
    def base_path(self) -> Path:
        return self._base

    def _validate_path(self, relative: str) -> Path:
        """Resolve a relative path and ensure it stays within the base directory."""
        target = (self._base / relative).resolve()
        if not str(target).startswith(str(self._base)):
            raise ValueError(f"Path traversal denied: {relative}")
        return target

    def read(self, path: str) -> str:
        """Read a file from the knowledge base."""
        target = self._validate_path(path)
        if not target.is_file():
            raise FileNotFoundError(f"Not found: {path}")
        return target.read_text(encoding="utf-8")

    def write(self, path: str, content: str, append: bool = False) -> None:
        """Write or append to a file in the knowledge base."""
        target = self._validate_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(target, mode, encoding="utf-8") as f:
            f.write(content)

    def list_files(self, directory: str = ".", pattern: str = "*") -> list[str]:
        """List files in a directory, optionally filtered by glob pattern."""
        target = self._validate_path(directory)
        if not target.is_dir():
            return []
        results = []
        for p in sorted(target.rglob(pattern)):
            if p.is_file():
                results.append(str(p.relative_to(self._base)))
        return results

    def search(self, text: str, directory: str = ".") -> list[dict[str, str]]:
        """Search for a string across all files in the knowledge base."""
        target = self._validate_path(directory)
        if not target.is_dir():
            return []
        matches = []
        for p in sorted(target.rglob("*")):
            if not p.is_file():
                continue
            try:
                content = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            for i, line in enumerate(content.splitlines(), 1):
                if text.lower() in line.lower():
                    matches.append({
                        "file": str(p.relative_to(self._base)),
                        "line": i,
                        "content": line.strip(),
                    })
        return matches

    def exists(self, path: str) -> bool:
        """Check if a path exists in the knowledge base."""
        try:
            target = self._validate_path(path)
            return target.exists()
        except ValueError:
            return False
