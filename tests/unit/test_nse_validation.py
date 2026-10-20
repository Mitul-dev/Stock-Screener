"""Source identity, turnover and delivery validation before publication."""

from datetime import date

import polars as pl
import pytest

from equity_engine.ingestion.validator import DataValidator


@pytest.mark.parametrize("column,value", [
    ("date", None), ("instrument_id", None), ("symbol", " "),
    ("traded_value", -1.0), ("traded_value", float("nan")),
    ("deliverable_quantity", 1001.0), ("deliverable_pct", 101.0),
])
def test_invalid_source_metadata_is_rejected(column, value):
    frame = pl.DataFrame({
        "date": [date(2026, 10, 8)], "instrument_id": ["INE002A01018"],
        "symbol": ["RELIANCE"], "series": ["EQ"],
        "open": [100.0], "high": [102.0], "low": [99.0], "close": [101.0],
        "volume": [1000.0], "traded_value": [100500.0],
        "deliverable_quantity": [None], "deliverable_pct": [None],
    }, schema_overrides={"deliverable_quantity": pl.Float64, "deliverable_pct": pl.Float64})
    frame = frame.with_columns(pl.lit(value, dtype=frame.schema[column]).alias(column))
    with pytest.raises(ValueError):
        DataValidator.validate_ohlcv(frame)


def test_untyped_optional_null_delivery_is_valid():
    frame = pl.DataFrame({
        "date": [date(2026, 10, 8)], "open": [100.0], "high": [102.0],
        "low": [99.0], "close": [101.0], "volume": [1000.0],
        "deliverable_quantity": [None], "deliverable_pct": [None],
    })
    DataValidator.validate_ohlcv(frame)
