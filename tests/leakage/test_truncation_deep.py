import polars as pl
from datetime import date, timedelta
import numpy as np

def test_truncation():
    # 1. Create dataset B (Full dataset)
    dates = [date(2023, 1, 1) + timedelta(days=i) for i in range(100)]
    df_b = pl.DataFrame({
        "symbol": ["INST-1"] * 100,
        "date": dates,
        "open": [float(100 + i) for i in range(100)],
        "high": [float(105 + i) for i in range(100)],
        "low": [float(95 + i) for i in range(100)],
        "close": [float(102 + i) for i in range(100)],
        "volume": [1000.0 * (1 + i/100) for i in range(100)]
    })
    
    # 2. Create dataset A (Truncated to day 50, index 49)
    df_a = df_b.head(50)
    
    # 3. Calculate features
    from equity_engine.features.calculator import FeatureCalculator
    feat_b = FeatureCalculator.calculate_features(df_b)
    feat_a = FeatureCalculator.calculate_features(df_a)
    
    row_b = feat_b.row(49, named=True)
    row_a = feat_a.row(49, named=True)
    
    assert row_a["sma_50"] == row_b["sma_50"], "SMA 50 leaked"
    assert row_a["sma_200"] == row_b["sma_200"], "SMA 200 leaked"
    assert row_a["vol_rel_20"] == row_b["vol_rel_20"], "vol_rel_20 leaked"
    assert row_a["atr_14"] == row_b["atr_14"], "atr_14 leaked"
    assert row_a["atr_pct"] == row_b["atr_pct"], "atr_pct leaked"
    
    # Check VCB 
    from equity_engine.setups.vcb import VCBDetector
    vcb_detector = VCBDetector({"parameters": {"lookback_days": 10, "max_atr_percentile": 0.5, "min_consolidation_days": 5}})
    events_b = vcb_detector.detect("INST-1", feat_b)
    events_a = vcb_detector.detect("INST-1", feat_a)
    
    # Count how many events in events_b are <= day 49
    b_events_upto_49 = [e for e in events_b if e.timestamp <= dates[49]]
    
    assert len(events_a) == len(b_events_upto_49), "VCB events count differs"
    for ea, eb in zip(events_a, b_events_upto_49):
        assert ea.timestamp == eb.timestamp, "VCB timestamps differ"
        assert ea.breakout_level == eb.breakout_level, "VCB breakout levels differ"
    
if __name__ == "__main__":
    test_truncation()
    print("Passed truncation test!")
