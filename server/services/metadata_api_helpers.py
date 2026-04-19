"""Shared response shaping for metadata list endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, TypeVar

from crud.base import model_to_dict

T = TypeVar("T")


def paginated_model_rows(rows: List[T], skip: int, limit: int) -> Dict[str, Any]:
    total = len(rows)
    page = rows[skip : skip + limit]
    return {
        "data": [model_to_dict(item) for item in page],
        "total": total,
        "page": (skip // limit) + 1 if limit > 0 else 1,
        "limit": limit,
    }
