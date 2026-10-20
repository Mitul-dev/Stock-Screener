import pytest
import polars as pl
from datetime import date, timedelta
from equity_engine.features.calculator import FeatureCalculator

def test_feature_calculator():
    dates = [date(2023, 1, 1) + timedelta(days=i) for i in range(300)]
    
    # Create simple upward trend
    df = pl.DataFrame({
        "date": dates,
        "open": [100.0 + i for i in range(300)],
        "high": [102.0 + i for i in range(300)],
        "low": [99.0 + i for i in range(300)],
        "close": [101.0 + i for i in range(300)],
        "volume": [1000.0] * 300
    })
    
    features = FeatureCalculator.calculate_features(df)
    
    # TR should be max(102-99, abs(102-prev_close), abs(99-prev_close))
    # For day 1 (index 1, prev_close=101):
    # max(3, abs(103-101)=2, abs(100-101)=1) = 3
    assert features["tr"][1] == 3.0
    
    # ATR should be 3.0 since TR is always 3.0 (except first day which is null)
    # Wait, first day prev_close is null, so TR is max(3, null, null) -> null in polars?
    # max_horizontal with nulls ignores nulls in polars if not all null.
    # So day 0 TR is max(3, null, null) = 3.0
    assert features["atr_14"][15] == 3.0
    
    # vol_rel_20 should be 1.0 since volume is constant
    assert features["vol_rel_20"][25] == 1.0
    
    # high_252d at day 255 should be the max high from day 3 to 254 (which is high of day 254)
    # high of day 254 is 102 + 254 = 356
    assert features["high_252d"][255] == 356.0
    
    # std_20
    assert features["std_20"][30] is not None
