"""Pure-function tests for services.row_corruption (no DB)."""

from unittest.mock import MagicMock, patch

from services.row_corruption import merge_corruption_pairs


def _pk_mapper(pk_key: str = "id"):
    mapper = MagicMock()
    pk_col = MagicMock()
    pk_col.key = pk_key
    mapper.primary_key = [pk_col]
    return mapper


def _table_columns(*names: str):
    cols = []
    for n in names:
        c = MagicMock()
        c.name = n
        c.key = n
        cols.append(c)
    return cols


def test_merge_corruption_pairs_collapses_duplicate_primary_key():
    model_cls = MagicMock()
    model_cls.__table__ = MagicMock(
        columns=_table_columns("id", "name", "original_csv_row_id")
    )
    main = MagicMock()
    main.id = 7
    main.name = "x"

    with patch("services.row_corruption.inspect", return_value=_pk_mapper("id")), patch(
        "services.row_corruption.model_to_dict", return_value={"id": 7, "name": "x"}
    ):
        out = merge_corruption_pairs([(main, None), (main, None)], model_cls)

    assert len(out) == 1
    assert out[0]["_is_corrupted"] is False
    assert out[0]["_error_context"] is None


def test_merge_corruption_pairs_sets_error_context_when_main_empty_sidecar_filled():
    model_cls = MagicMock()
    model_cls.__table__ = MagicMock(
        columns=_table_columns("id", "name", "original_csv_row_id")
    )
    main = MagicMock()
    main.id = 1
    main.name = None
    side = MagicMock()
    side.name = "raw"
    side.error_reason = "encoding"

    with patch("services.row_corruption.inspect", return_value=_pk_mapper("id")), patch(
        "services.row_corruption.model_to_dict", return_value={"id": 1, "name": None}
    ):
        out = merge_corruption_pairs([(main, side)], model_cls)

    assert len(out) == 1
    assert out[0]["_is_corrupted"] is True
    assert out[0]["_error_context"]["name"]["raw_value"] == "raw"
    assert out[0]["_error_context"]["name"]["error"] == "encoding"


def test_merge_treats_blank_string_main_as_missing():
    model_cls = MagicMock()
    model_cls.__table__ = MagicMock(
        columns=_table_columns("id", "name", "original_csv_row_id")
    )
    main = MagicMock()
    main.id = 1
    main.name = "   "
    side = MagicMock()
    side.name = "raw"
    side.error_reason = "x"

    with patch("services.row_corruption.inspect", return_value=_pk_mapper("id")), patch(
        "services.row_corruption.model_to_dict", return_value={"id": 1, "name": "   "}
    ):
        out = merge_corruption_pairs([(main, side)], model_cls)

    assert out[0]["_is_corrupted"] is True
    assert "name" in out[0]["_error_context"]
