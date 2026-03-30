"""Logging utilities used across the project."""

from __future__ import annotations

import logging
import sys
from functools import lru_cache


@lru_cache(maxsize=1)
def configure_logging(level: int = logging.INFO) -> None:
    """Configure application-wide logging once."""

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
