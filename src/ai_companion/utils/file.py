"""
File utilities.
"""

import os
from pathlib import Path
from typing import Optional
from contextlib import contextmanager


def safe_read_file(path: Path, encoding: str = "utf-8") -> Optional[str]:
    """Safely read a file, returning None if it doesn't exist or can't be read."""
    try:
        return path.read_text(encoding=encoding)
    except (OSError, UnicodeDecodeError):
        return None


def safe_write_file(path: Path, content: str, encoding: str = "utf-8") -> bool:
    """Safely write content to a file, creating parent directories if needed."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding=encoding)
        return True
    except OSError:
        return False


def ensure_directory(path: Path) -> bool:
    """Ensure a directory exists, creating it if necessary."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False


@contextmanager
def atomic_write(path: Path, mode: str = "w", encoding: str = "utf-8"):
    """Atomically write to a file using a temporary file."""
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        if mode == "w":
            with temp_path.open(mode, encoding=encoding) as f:
                yield f
        else:
            with temp_path.open(mode) as f:
                yield f
        temp_path.replace(path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
