"""
Corruption sidecar merge for dynamic table APIs.

DLT ingested tables have a clean main row plus optional rows in ``{table}__corrupted``
(or legacy ``corrupted_rows``) keyed by ``original_csv_row_id``. This module resolves
the sidecar model, runs one SQL join or one batched sidecar query, and produces the
same JSON row shape the UI expects.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_class_strict
from crud.base import model_to_dict

logger = logging.getLogger(__name__)

_LEGACY_SIDECAR = "corrupted_rows"
_INTERNAL_COL_NAMES = frozenset({"id", "original_csv_row_id"})


def _sidecar_label(sidecar: Any) -> str:
    try:
        return str(sidecar.__table__.fullname)
    except AttributeError:
        return repr(sidecar)


def resolve_sidecar_class(table_name: str) -> Optional[Any]:
    schema = settings.DLT_DATASET
    dedicated = f"{table_name}__corrupted"
    cls_d = get_class_strict(dedicated, schema)
    if cls_d is not None:
        return cls_d
    cls_l = get_class_strict(_LEGACY_SIDECAR, schema)
    if cls_l is not None:
        logger.warning(
            "row_corruption: dedicated sidecar %r not in reflection; falling back to %r "
            "for main table %r (merge keys may not match this upload)",
            dedicated,
            _LEGACY_SIDECAR,
            table_name,
        )
    return cls_l


def corruption_merge_eligible(main_model: Any, sidecar_model: Optional[Any]) -> bool:
    return bool(
        sidecar_model
        and hasattr(main_model, "original_csv_row_id")
        and hasattr(sidecar_model, "original_csv_row_id")
    )


def _value_missing_on_main(main_val: Any) -> bool:
    """True when the clean row has no usable value but the sidecar may hold the raw input."""
    if main_val is None:
        return True
    if isinstance(main_val, str) and main_val.strip() == "":
        return True
    return False


def merge_corruption_pairs(
    pairs: Sequence[Tuple[Any, Any]],
    model_class: Any,
) -> List[Dict[str, Any]]:
    """
    Collapse (main, corrupted?) join rows to one dict per primary key with
    ``_is_corrupted`` and ``_error_context``. Pure over in-memory ORM rows.

    Uses ``Table.columns`` so dict keys match :func:`crud.base.model_to_dict`
    (column ``name``), while attribute reads use ``column.key``.
    """
    pk_key = inspect(model_class).primary_key[0].key
    aggregated: Dict[Any, Dict[str, Any]] = {}
    order: List[Any] = []

    for main_row, corrupted_row in pairs:
        pk_val = getattr(main_row, pk_key)
        if pk_val not in aggregated:
            order.append(pk_val)
            aggregated[pk_val] = {"main_row": main_row, "corrupted_rows": []}
        if corrupted_row is not None:
            aggregated[pk_val]["corrupted_rows"].append(corrupted_row)

    out: List[Dict[str, Any]] = []
    table_columns = list(model_class.__table__.columns)

    for pk_val in order:
        bundle = aggregated[pk_val]
        main_row = bundle["main_row"]
        item_dict = model_to_dict(main_row)
        error_context: Dict[str, Any] = {}
        for corrupted_row in bundle["corrupted_rows"]:
            for col in table_columns:
                if col.name in _INTERNAL_COL_NAMES:
                    continue
                main_val = getattr(main_row, col.key, None)
                corrupt_val = getattr(corrupted_row, col.key, None)
                if _value_missing_on_main(main_val) and corrupt_val is not None:
                    if col.name not in error_context:
                        error_context[col.name] = {
                            "raw_value": str(corrupt_val),
                            "error": getattr(corrupted_row, "error_reason", None)
                            or "Validation failed",
                        }
        if error_context:
            item_dict["_is_corrupted"] = True
            item_dict["_error_context"] = error_context
        else:
            item_dict["_is_corrupted"] = False
            item_dict["_error_context"] = None
        out.append(item_dict)
    return out


def query_joined_page(
    db: Session,
    main_model: Any,
    sidecar_model: Any,
    skip: int,
    limit: int,
) -> List[Tuple[Any, Any]]:
    mapper = inspect(main_model)
    pk_order = list(mapper.primary_key)
    stmt = select(main_model, sidecar_model).outerjoin(
        sidecar_model,
        main_model.original_csv_row_id == sidecar_model.original_csv_row_id,
    )
    if pk_order:
        stmt = stmt.order_by(*(c.asc() for c in pk_order))
    stmt = stmt.offset(skip).limit(limit)
    return db.execute(stmt).all()


def expand_main_rows_to_pairs(
    db: Session,
    sidecar_model: Any,
    main_rows: Sequence[Any],
) -> List[Tuple[Any, Any]]:
    oids = [
        oid
        for oid in (
            getattr(row, "original_csv_row_id", None) for row in main_rows
        )
        if oid is not None
    ]
    by_oid: Dict[Any, List[Any]] = defaultdict(list)
    if oids:
        q = db.query(sidecar_model).filter(sidecar_model.original_csv_row_id.in_(oids))
        for cr in q.all():
            by_oid[cr.original_csv_row_id].append(cr)

    pairs: List[Tuple[Any, Any]] = []
    for item in main_rows:
        oid = getattr(item, "original_csv_row_id", None)
        sidecars = by_oid.get(oid, []) if oid is not None else []
        if not sidecars:
            pairs.append((item, None))
        else:
            for cr in sidecars:
                pairs.append((item, cr))
    return pairs


def serialize_main_rows(
    db: Session,
    model_class: Any,
    table_name: str,
    main_rows: Sequence[Any],
) -> List[Dict[str, Any]]:
    """Dicts for API ``data``; merges sidecar when this table supports it."""
    sidecar = resolve_sidecar_class(table_name)
    if not corruption_merge_eligible(model_class, sidecar):
        return [model_to_dict(r) for r in main_rows]
    pairs = expand_main_rows_to_pairs(db, sidecar, main_rows)
    return merge_corruption_pairs(pairs, model_class)


def fetch_merged_page_or_none(
    db: Session,
    model_class: Any,
    table_name: str,
    skip: int,
    limit: int,
) -> Optional[Tuple[List[Dict[str, Any]], int]]:
    """
    If this table supports corruption merge, return (serialized rows, total count).
    Otherwise return None so the caller can use the repository path.
    """
    facade = RowCorruptionFacade(db, model_class, table_name)
    if not facade.merge_enabled:
        if facade._sidecar is None:
            logger.info(
                "row_corruption: skip merge table=%r — no sidecar class "
                "(look for schema %r table %r__corrupted after ETL + /api/refresh)",
                table_name,
                settings.DLT_DATASET,
                table_name,
            )
        elif not hasattr(model_class, "original_csv_row_id"):
            logger.info(
                "row_corruption: skip merge table=%r — main ORM model has no original_csv_row_id",
                table_name,
            )
        elif facade._sidecar is not None and not hasattr(
            facade._sidecar, "original_csv_row_id"
        ):
            logger.info(
                "row_corruption: skip merge table=%r — sidecar %s has no original_csv_row_id",
                table_name,
                _sidecar_label(facade._sidecar),
            )
        return None
    data, total = facade.fetch_dict_page(skip, limit)
    flagged = sum(1 for row in data if row.get("_is_corrupted"))
    logger.info(
        "row_corruption: merged table=%r sidecar=%s main_total=%s page_len=%s "
        "rows_with_errors=%s",
        table_name,
        _sidecar_label(facade._sidecar),
        total,
        len(data),
        flagged,
    )
    return data, total


def delete_sidecar_rows_for_original_id(
    db: Session,
    table_name: str,
    original_csv_row_id: Any,
    *,
    log_context: str = "",
) -> None:
    """Remove sidecar rows for one logical CSV row; logs and swallows DB errors."""
    if original_csv_row_id is None:
        return
    sidecar = resolve_sidecar_class(table_name)
    if not sidecar:
        return
    try:
        db.query(sidecar).filter(
            sidecar.original_csv_row_id == original_csv_row_id
        ).delete()
        db.commit()
    except Exception as e:
        logger.warning(
            "%sFailed to delete corruption sidecar rows for original_csv_row_id=%s: %s",
            f"{log_context} " if log_context else "",
            original_csv_row_id,
            e,
        )


class RowCorruptionFacade:
    """
    Facade for corruption sidecar resolution and serialization (single entry style
    for routes that already hold db, model, and table_name).
    """

    def __init__(self, db: Session, main_model: Any, table_name: str):
        self.db = db
        self.main_model = main_model
        self.table_name = table_name
        self._sidecar = resolve_sidecar_class(table_name)

    @property
    def merge_enabled(self) -> bool:
        return corruption_merge_eligible(self.main_model, self._sidecar)

    def fetch_dict_page(self, skip: int, limit: int) -> Tuple[List[Dict[str, Any]], int]:
        """Paginated API rows with corruption merged; caller must ensure merge_enabled."""
        total = self.db.query(self.main_model).count()
        raw_pairs = query_joined_page(
            self.db, self.main_model, self._sidecar, skip, limit
        )
        data = merge_corruption_pairs(raw_pairs, self.main_model)
        return data, total

    def serialize_main_rows(self, main_rows: Sequence[Any]) -> List[Dict[str, Any]]:
        return serialize_main_rows(self.db, self.main_model, self.table_name, main_rows)

    def delete_sidecar_for_original_id(self, original_csv_row_id: Any, *, log_context: str = "") -> None:
        delete_sidecar_rows_for_original_id(
            self.db, self.table_name, original_csv_row_id, log_context=log_context
        )
