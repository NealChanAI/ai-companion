"""
Logging configuration.
"""

import logging
import sys
from typing import Optional
from pathlib import Path


def setup_logging(level: str = "INFO", file_path: Optional[Path] = None) -> None:
    """Setup logging based on configuration."""
    level_num = getattr(logging, level.upper(), logging.INFO)

    handlers = []
    handlers.append(logging.StreamHandler(sys.stdout))

    if file_path is not None:
        file_path.parent.mkdir(exist_ok=True, parents=True)
        handlers.append(logging.FileHandler(file_path))

    logging.basicConfig(
        level=level_num,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger by name."""
    return logging.getLogger(name)
