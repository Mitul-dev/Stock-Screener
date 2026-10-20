import pytest
import polars as pl
from datetime import date, timedelta
from equity_engine.setups.breakout import SetupEvent
from equity_engine.outcomes.engine import OutcomeEngine
from equity_engine.backtest.engine import ResearchEngine

def test_research_engine_split():
    engine = ResearchEngine(None)
    
    dates = [date(2023, 1, 1) + timedelta(days=i) for i in range(1000)]
    df = pl.DataFrame({
        "date": dates,
        "close": range(1000)
    })
    
    disc, val, hold = engine.split_data(df, 0.6, 0.2)
    
    assert len(disc) > 0
    assert len(val) > 0
    assert len(hold) > 0
    
    assert disc["date"].max() < val["date"].min()
    assert val["date"].max() < hold["date"].min()

def test_research_engine_backtest():
    outcome_engine = OutcomeEngine({"timeout_days": 3})
    research_engine = ResearchEngine(outcome_engine)
    
    event1 = SetupEvent(
        instrument_id="INST-1",
        setup_version="BREAKOUT_V1.0",
        timestamp=date(2023, 1, 1),
        breakout_level=100.0,
        features={"atr_14": 4.0}
    )
    
    df = pl.DataFrame({
        "instrument_id": ["INST-1"] * 4,
        "date": [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)],
        "open": [100.0, 102.0, 100.0, 95.0],
        "high": [101.5, 105.0, 102.0, 96.0],
        "low": [99.0, 101.0, 97.0, 90.0],
        "close": [101.0, 103.0, 98.0, 92.0]
    })
    
    results = research_engine.run_backtest([event1], df)
    
    assert len(results) == 1
    assert results["final_state"][0] == "FAILED"
    assert results["gross_realized_r"][0] == -1.0
