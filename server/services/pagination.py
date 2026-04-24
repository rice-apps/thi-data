"""Shared pagination envelope for list/search API responses."""

from typing import Any, Dict, List


def paginated_dict(data: List[Any], total: int, skip: int, limit: int) -> Dict[str, Any]:
    """Same shape as legacy rows endpoints: data, total, page, limit."""
    return {
        "data": data,
        "total": total,
        "page": (skip // limit) + 1,
        "limit": limit,
    }
