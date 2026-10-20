from datetime import date

import polars as pl
import pytest

from equity_engine.corporate_actions.adjustor import CorporateActionAdjustor
from equity_engine.universe.builder import UniverseBuilder


def bars(dates, prices, volumes):
    return pl.DataFrame({
        "date": dates,
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
        "volume": volumes,
    })


def test_split_applies_when_security_has_no_ex_date_bar():
    raw = bars([date(2024, 1, 2), date(2024, 1, 4)], [100.0, 50.0], [1000.0, 2000.0])
    actions = pl.DataFrame({"date": [date(2024, 1, 3)], "action_type": ["SPLIT"], "factor": [2.0]})

    adjusted = CorporateActionAdjustor.adjust_ohlcv(raw, actions)

    assert adjusted["close"].to_list() == [100.0, 50.0]
    assert adjusted["adj_close"].to_list() == [50.0, 50.0]
    assert adjusted["adj_volume"].to_list() == [2000.0, 2000.0]
    assert adjusted["adj_factor"].to_list() == [2.0, 1.0]
    assert adjusted.height == raw.height
    with pytest.raises(ValueError, match="already-adjusted"):
        CorporateActionAdjustor.adjust_ohlcv(adjusted, actions)


def test_no_action_keeps_raw_prices_and_volume():
    raw = bars([date(2024, 1, 2)], [100.0], [1000.0])
    actions = pl.DataFrame(schema={"date": pl.Date, "factor": pl.Float64})

    adjusted = CorporateActionAdjustor.adjust_ohlcv(raw, actions)

    assert adjusted["adj_close"].to_list() == raw["close"].to_list()
    assert adjusted["adj_volume"].to_list() == raw["volume"].to_list()
    assert adjusted["adj_factor"].to_list() == [1.0]


@pytest.mark.parametrize("factor", [0.0, -2.0, float("nan"), float("inf"), None])
def test_invalid_action_factor_is_rejected(factor):
    raw = bars([date(2024, 1, 2)], [100.0], [1000.0])
    actions = pl.DataFrame({"date": [date(2024, 1, 3)], "factor": [factor]})
    with pytest.raises(ValueError, match="finite and positive"):
        CorporateActionAdjustor.adjust_ohlcv(raw, actions)


def test_null_action_date_is_rejected():
    raw = bars([date(2024, 1, 2)], [100.0], [1000.0])
    actions = pl.DataFrame({"date": pl.Series([None], dtype=pl.Date), "factor": [2.0]})
    with pytest.raises(ValueError, match="dates cannot be null"):
        CorporateActionAdjustor.adjust_ohlcv(raw, actions)


def universe_builder():
    return UniverseBuilder({"liquidity_tiers": {"tier_1": {
        "min_median_traded_value": 50000,
        "min_trading_days_coverage": 1.0,
        "min_price": 50,
    }}})


def test_universe_uses_latest_observed_price_and_preserves_official_turnover():
    history = pl.DataFrame({
        "instrument_id": ["ISIN_A"] * 3,
        "symbol": ["A"] * 3,
        "date": [date(2024, 1, 3), date(2024, 1, 2), date(2024, 1, 4)],
        "close": [30.0, 100.0, 200.0],
        "volume": [10000.0] * 3,
        "traded_value": [60000.0] * 3,
    })
    # The latest observable price is 30: neither the earlier price of 100 nor
    # the future price of 200 may make this instrument eligible.
    assert universe_builder().build_daily_universe(date(2024, 1, 3), history, 2).is_empty()
    # Even with enormous computed close * volume, official turnover below the
    # configured threshold must exclude the security.
    low_turnover = history.with_columns(pl.lit(1000.0).alias("traded_value"), pl.lit(100.0).alias("close"))
    assert universe_builder().build_daily_universe(date(2024, 1, 3), low_turnover, 2).is_empty()


def test_universe_does_not_merge_instruments_with_reused_symbol():
    history = pl.DataFrame({
        "instrument_id": ["ISIN_A", "ISIN_A", "ISIN_B", "ISIN_B"],
        "symbol": ["REUSED"] * 4,
        "date": [date(2024, 1, 2), date(2024, 1, 3)] * 2,
        "close": [100.0, 100.0, 10.0, 10.0],
        "volume": [1000.0] * 4,
        "traded_value": [60000.0] * 4,
    })

    eligible = universe_builder().build_daily_universe(date(2024, 1, 3), history, 2)

    assert eligible.select("instrument_id", "symbol", "tier").to_dicts() == [
        {"instrument_id": "ISIN_A", "symbol": "REUSED", "tier": "tier_1"}
    ]
    assert eligible["median_traded_value"].to_list() == [60000.0]
    assert eligible["days_traded"].to_list() == [2]
    assert eligible["coverage"].to_list() == [1.0]
    assert eligible["latest_price"].to_list() == [100.0]
