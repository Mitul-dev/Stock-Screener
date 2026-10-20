import pytest
import polars as pl
from datetime import date
from equity_engine.setups.breakout import SetupEvent, SetupState
from equity_engine.outcomes.engine import OutcomeEngine

def test_outcome_engine():
    engine = OutcomeEngine({"timeout_days": 3})
    
    event = SetupEvent(
        instrument_id="INST-1",
        setup_version="BREAKOUT_V1.0",
        timestamp=date(2023, 1, 1),
        breakout_level=100.0,
        features={"atr_14": 4.0}
    )
    
    # 4 days total. Day 1 is detection.
    # Breakout level 100.0, stop level 100 - 0.5*4 = 98.0
    # Day 1: close = 101.0 (confirmed)
    # Day 2: open = 102.0 (entry). high = 105.0. low = 101.0. close = 103.0
    # Day 3: low drops to 97.0, hitting stop. open was 100.0.
    
    df = pl.DataFrame({
        "date": [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)],
        "open": [100.0, 102.0, 100.0, 95.0],
        "high": [101.5, 105.0, 102.0, 96.0],
        "low": [99.0, 101.0, 97.0, 90.0],
        "close": [101.0, 103.0, 98.0, 92.0]
    })
    
    res = engine.evaluate_event(event, df)
    
    assert res["final_state"] == SetupState.FAILED.value
    assert res["confirmation_date"] == date(2023, 1, 1)
    assert res["entry_price"] == 102.0
    assert res["stop_price"] == 98.0
    
    risk = 102.0 - 98.0 # 4.0
    
    assert res["exit_date"] == date(2023, 1, 3)
    assert res["exit_price"] == 98.0 # didn't gap below stop (open was 100, low 97, exit at stop 98)
    assert res["gross_realized_r"] == -1.0
    assert res["net_realized_r"] < -1.0 # Due to fees
    
    # MFE was high of Day 2 = 105.0. (105-102)/4 = 3.0 / 4 = 0.75
    assert res["mfe"] == 0.75
    # MAE was 97.0. (97-102)/4 = -5 / 4 = -1.25
    assert res["mae"] == -1.25
