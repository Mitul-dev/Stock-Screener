"""Independent acceptance checks; run explicitly, outside the existing test suite.

These assert required behavior, not the current defects. Failures identify repair
work for the implementation owner. No network, raw-data writes, or notifications.
"""
from datetime import date, timedelta

import polars as pl
import pytest

from equity_engine.backtest.controls import ControlEngine
from equity_engine.corporate_actions.adjustor import CorporateActionAdjustor
from equity_engine.features.calculator import FeatureCalculator
from equity_engine.ingestion.nse_importer import NSEImporter
from equity_engine.ingestion.validator import DataValidator
from equity_engine.outcomes.engine import OutcomeEngine
from equity_engine.setups.breakout import SetupEvent
from equity_engine.universe.builder import UniverseBuilder


def bar():
    return pl.DataFrame({"date": [date(2024, 1, 1)], "open": [100.],
                         "high": [101.], "low": [99.], "close": [100.],
                         "volume": [1000.]})


@pytest.mark.parametrize("column,value", [("open", None), ("volume", float("inf")),
                                         ("close", 0.)])
def test_validator_rejects_missing_nonfinite_or_zero_prices(column, value):
    df = bar().with_columns(pl.lit(value, dtype=pl.Float64).alias(column))
    if column == "close":
        df = df.with_columns(pl.lit(0.).alias("low"))
    with pytest.raises(ValueError):
        DataValidator.validate_ohlcv(df)


def test_multi_instrument_bars_are_not_duplicate_dates():
    df = pl.concat([bar().with_columns(pl.lit(x).alias("instrument_id"))
                    for x in ["A", "B"]])
    DataValidator.validate_ohlcv(df)


def test_importer_preserves_available_delivery(tmp_path):
    # Exercise the importer's existing accepted header spelling, independently
    # of whether that spelling matches the real exchange format.
    df = pl.DataFrame({"TradDt": ["2024-01-01"], "ISIN": ["INE002A01018"],
                       "TckrSymb": ["RELIANCE"], "SctySrs": ["EQ"],
                       "OpnPric": [100.], "HghPric": [101.], "LwPric": [99.],
                       "ClsPric": [100.], "TtlTradgVol": [1000],
                       "TtlTrfVal": [100000.], "DlvblQty": [500.],
                       "DlvblPct": [50.]})
    importer = NSEImporter(str(tmp_path), str(tmp_path / "processed"))
    normalized = importer._parse_consolidated(df)
    assert normalized["deliverable_quantity"][0] == 500.
    assert normalized["deliverable_pct"][0] == 50.


def universe_config():
    return {"liquidity_tiers": {"tier_1": {
        "min_median_traded_value": 50000., "min_trading_days_coverage": .95,
        "min_price": 50.}}}


def test_universe_excludes_stale_history_outside_window():
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(120)]
    stale = pl.DataFrame({"date": dates[:60], "symbol": ["STALE"] * 60,
                          "close": [100.] * 60, "volume": [1000.] * 60})
    active = pl.DataFrame({"date": dates, "symbol": ["ACTIVE"] * 120,
                           "close": [100.] * 120, "volume": [1000.] * 120})
    result = UniverseBuilder(universe_config()).build_daily_universe(
        dates[-1], pl.concat([stale, active]), lookback_days=60)
    assert "STALE" not in result["symbol"].to_list()


def test_universe_uses_reported_turnover():
    # A daily close is not the average traded price: use source turnover.
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(60)]
    df = pl.DataFrame({"date": dates, "symbol": ["A"] * 60,
                       "close": [100.] * 60, "volume": [600.] * 60,
                       "traded_value": [40000.] * 60})
    result = UniverseBuilder(universe_config()).build_daily_universe(dates[-1], df)
    assert result.is_empty()


def test_incomplete_watch_is_censored_not_expired():
    event = SetupEvent("A", "BREAKOUT_V1", date(2024, 1, 1), 102., {"atr_14": 4.})
    outcome = OutcomeEngine({"watch_expiry_days": 5}).evaluate_event(event, bar())
    assert outcome["final_state"] == "WATCH"


def test_stop_uses_confirmation_atr():
    event = SetupEvent("A", "BREAKOUT_V1", date(2024, 1, 1), 100., {"atr_14": 4.})
    df = pl.DataFrame({"date": [date(2024, 1, i) for i in (1, 2, 3)],
                       "open": [99., 100., 102.], "high": [100., 102., 104.],
                       "low": [98., 99., 101.], "close": [99., 101., 103.],
                       "atr_14": [4., 10., 10.]})
    outcome = OutcomeEngine({}).evaluate_event(event, df)
    assert outcome["stop_price"] == 95.  # 100 - 0.5 * confirmation ATR 10


def test_one_profitable_observation_cannot_validate_evidence():
    stats = ControlEngine.calculate_metrics(pl.DataFrame({"net_realized_r": [1.]}))
    assert stats["status"] == "INSUFFICIENT EVIDENCE"


def test_existing_adjustment_to_feature_composition_uses_adjusted_prices():
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(20)]
    prices = [100.] * 15 + [50.] * 5
    raw = pl.DataFrame({"date": dates, "open": prices, "high": prices,
                        "low": prices, "close": prices,
                        "volume": [1000.] * 15 + [2000.] * 5})
    actions = pl.DataFrame({"date": [dates[15]], "factor": [2.]})
    adjusted = CorporateActionAdjustor.adjust_ohlcv(raw, actions)
    assert adjusted["adj_close"].to_list() == [50.] * 20
    # This is exactly the current pilot's composition. Correcting the caller
    # to explicitly select adjusted columns is sufficient; no redesign needed.
    features = FeatureCalculator.calculate_features(adjusted)
    assert features["tr"][15] == 0.


def test_next_session_entry_and_executable_gap_stop_work():
    event = SetupEvent("A", "BREAKOUT_V1", date(2024, 1, 1), 100., {"atr_14": 4.})
    df = pl.DataFrame({"date": [date(2024, 1, i) for i in (1, 2, 3)],
                       "open": [100., 102., 90.], "high": [102., 105., 94.],
                       "low": [99., 101., 88.], "close": [101., 103., 92.]})
    result = OutcomeEngine({}).evaluate_event(event, df)
    assert result["entry_price"] == 102.
    assert result["exit_price"] == 90.
    assert result["gross_realized_r"] == -3.


def test_confirm_requires_strict_close_above_level():
    event = SetupEvent("A", "BREAKOUT_V1", date(2024, 1, 1), 100., {"atr_14": 4.})
    result = OutcomeEngine({"watch_expiry_days": 1}).evaluate_event(event, bar())
    assert result["confirmation_date"] is None
    assert result["final_state"] == "EXPIRED"
