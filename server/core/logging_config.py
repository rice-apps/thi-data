"""Single place to configure process-wide logging (API, worker, and libraries)."""

from __future__ import annotations

import logging

_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s",
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    _configured = True
