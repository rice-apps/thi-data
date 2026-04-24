"""HTTP trigger for API server schema refresh (worker calls API container)."""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)


def refresh_api_server_schema(max_retries: int = 2) -> None:
    import core.config as config

    url = f"{config.settings.API_SERVER_URL}/api/refresh"
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, timeout=10)
            resp.raise_for_status()
            logger.info("API server schema refresh succeeded (attempt %s)", attempt + 1)
            return
        except Exception as e:
            logger.warning("API server refresh attempt %s failed: %s", attempt + 1, e)
            if attempt == max_retries - 1:
                raise RuntimeError(
                    f"API server refresh failed after {max_retries} attempts: {e}"
                ) from e
