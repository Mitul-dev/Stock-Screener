import pytest
import polars as pl
from datetime import date
from equity_engine.corporate_actions.adjustor import CorporateActionAdjustor

def test_corporate_action_adjustor():
    ohlcv = pl.DataFrame({
        "date": [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)],
        "open": [100.0, 100.0, 50.0, 50.0],
        "high": [100.0, 100.0, 50.0, 50.0],
        "low": [100.0, 100.0, 50.0, 50.0],
        "close": [100.0, 100.0, 50.0, 50.0],
        "volume": [1000.0, 1000.0, 2000.0, 2000.0]
    })
    
    actions = pl.DataFrame({
        "date": [date(2023, 1, 3)],
        "action_type": ["SPLIT"],
        "factor": [2.0]  # 2:1 split
    })
    
    adj_df = CorporateActionAdjustor.adjust_ohlcv(ohlcv, actions)
    
    # Check adj_factor
    factors = adj_df["adj_factor"].to_list()
    assert factors == [2.0, 2.0, 1.0, 1.0]
    
    # Check adj_close
    closes = adj_df["adj_close"].to_list()
    assert closes == [50.0, 50.0, 50.0, 50.0]
    
    # Check adj_volume
    vols = adj_df["adj_volume"].to_list()
    assert vols == [2000.0, 2000.0, 2000.0, 2000.0]

def test_no_actions():
    ohlcv = pl.DataFrame({
        "date": [date(2023, 1, 1)],
        "open": [100.0],
        "high": [100.0],
        "low": [100.0],
        "close": [100.0],
        "volume": [1000.0]
    })
    actions = pl.DataFrame(schema={"date": pl.Date, "action_type": pl.String, "factor": pl.Float64})
    
    adj_df = CorporateActionAdjustor.adjust_ohlcv(ohlcv, actions)
    assert adj_df["adj_factor"][0] == 1.0
    assert adj_df["adj_close"][0] == 100.0
