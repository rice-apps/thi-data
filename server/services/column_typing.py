from __future__ import annotations

_ALIAS_TO_DUCKDB: dict[str, str] = {
    "STRING": "VARCHAR",
    "TEXT": "VARCHAR",
    "CHAR": "VARCHAR",
    "INT": "INTEGER",
    "FLOAT": "DOUBLE",
    "REAL": "DOUBLE",
    "BOOL": "BOOLEAN",
    "DATETIME": "TIMESTAMP",
}

_SUPPORTED = frozenset(
    {"VARCHAR", "INTEGER", "BIGINT", "DOUBLE", "BOOLEAN", "DATE", "TIMESTAMP"}
)


def quote_column_id(col_name: str) -> str:
    return f'"{col_name}"'


def normalize_duckdb_type(user_type: str) -> str:
    t = (user_type or "").strip().upper()
    t = _ALIAS_TO_DUCKDB.get(t, t)
    if t not in _SUPPORTED:
        return "VARCHAR"
    return t
