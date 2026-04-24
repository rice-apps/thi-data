"""Postgres LISTEN/NOTIFY for SSE-style frontend events."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import psycopg2

logger = logging.getLogger(__name__)


def publish_thi_event(event: Dict[str, Any], dsn: Optional[str] = None) -> None:
    """Publish JSON payload on channel ``thi_events`` (uses DLT/Postgres DSN by default)."""
    import core.config as config

    conn_str = dsn or config.settings.DLT_CREDENTIALS
    conn = psycopg2.connect(conn_str)
    try:
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cur:
            cur.execute("NOTIFY thi_events, %s;", (json.dumps(event),))
    finally:
        conn.close()
