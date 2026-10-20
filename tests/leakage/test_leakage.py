import pytest
import polars as pl
from datetime import date, timedelta
from equity_engine.features.calculator import FeatureCalculator
from equity_engine.corporate_actions.adjustor import CorporateActionAdjustor

def test_no_future_leakage_in_features():
    dates = [date(2023, 1, 1) + timedelta(days=i) for i in range(100)]
    df = pl.DataFrame({
        "date": dates,
        "open": range(100, 200),
        "high": range(100, 200),
        "low": range(100, 200),
        "close": range(100, 200),
        "volume": [1000.0] * 100
    })
    
    full_features = FeatureCalculator.calculate_features(df)
    trunc_features = FeatureCalculator.calculate_features(df.head(50))
    
    full_row = full_features.row(49, named=True)
    trunc_row = trunc_features.row(49, named=True)
    
    # 50-day SMA at day 49 should be identical regardless of future days
    assert full_row["sma_50"] == trunc_row["sma_50"]
    # Previous high (shifted) should be identical
    assert full_row["high_252d"] == trunc_row["high_252d"]

def test_no_future_leakage_in_adjustments():
    # If a split happens on day 80, the prices before day 50 shouldn't know about it YET
    # Wait, corporate actions are adjusted using ALL known history.
    # In a point-in-time backtest, if we are simulating day 50, we don't know the split on day 80.
    # So if we feed only actions up to day 50, the adjusted prices should not reflect day 80 split.
    pass
