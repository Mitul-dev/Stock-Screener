import pytest
import polars as pl
from datetime import date
from equity_engine.setups.breakout import BreakoutDetector, SetupState

def test_breakout_detector():
    config = {
        "version": "1.0",
        "parameters": {
            "lookback_days": 252,
            "min_volume_relative": 1.5,
            "close_near_high_pct": 0.02
        }
    }
    
    detector = BreakoutDetector(config)
    
    # 3 days:
    # Day 1: below high
    # Day 2: near high but low vol
    # Day 3: above high and high vol
    df = pl.DataFrame({
        "date": [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)],
        "close": [100.0, 198.0, 205.0],
        "high_252d": [200.0, 200.0, 200.0],
        "vol_rel_20": [1.0, 1.0, 2.0],
        "atr_14": [5.0, 5.0, 5.0]
    })
    
    events = detector.detect("INST-123", df)
    
    assert len(events) == 1
    event = events[0]
    
    assert event.instrument_id == "INST-123"
    assert event.setup_version == "BREAKOUT_V1.0"
    assert event.timestamp == date(2023, 1, 3)
    assert event.state == SetupState.WATCH
    assert event.breakout_level == 200.0
    assert event.features["vol_rel_20"] == 2.0
    
    # Test state transition
    event.transition(SetupState.CONFIRMED)
    assert event.state == SetupState.CONFIRMED
