import pytest
import polars as pl
from datetime import date
from equity_engine.setups.vcb import VCBDetector

def test_vcb_detector():
    config = {
        "version": "1.0",
        "parameters": {
            "lookback_days": 5,
            "max_atr_percentile": 0.50,
            "min_consolidation_days": 3
        }
    }
    
    detector = VCBDetector(config)
    
    # 5 days
    df = pl.DataFrame({
        "date": [date(2023, 1, i) for i in range(1, 7)],
        "close": [100.0, 100.0, 100.0, 101.0, 100.0, 105.0],
        "high": [101.0, 101.0, 101.0, 101.5, 101.0, 106.0],
        "atr_pct": [0.05, 0.04, 0.03, 0.02, 0.01, 0.01],
        "vol_rel_20": [1.0, 1.0, 1.0, 1.0, 1.0, 2.0],
        "atr_14": [5.0]*6
    })
    
    events = detector.detect("INST-123", df)
    
    # Consolidation high of day 6 is max(high) from day 3 to 5 = 101.5
    # Close on day 6 is 105.0 (breakout)
    # atr_pct on day 6 is 0.01. The past 5 days (days 2 to 6) atr_pct are [0.04, 0.03, 0.02, 0.01, 0.01]
    # 50th percentile is ~0.02. 0.01 <= 0.02, so is_contracted is True.
    # vol_rel_20 on day 6 is 2.0 >= 1.2
    
    assert len(events) == 1
    event = events[0]
    assert event.breakout_level == 101.5
    assert event.timestamp == date(2023, 1, 6)
