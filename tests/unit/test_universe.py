import pytest
import polars as pl
from datetime import date
from equity_engine.universe.builder import UniverseBuilder

def test_universe_builder():
    config = {
        "liquidity_tiers": {
            "tier_1": {
                "min_median_traded_value": 50000.0,
                "min_trading_days_coverage": 0.9,
                "min_price": 50.0
            },
            "tier_2": {
                "min_median_traded_value": 10000.0,
                "min_trading_days_coverage": 0.8,
                "min_price": 20.0
            }
        }
    }
    
    builder = UniverseBuilder(config)
    
    # 5 days for RELIANCE (tier 1), 4 days for TCS (tier 2), 2 days for PENNY (fail)
    ohlcv = pl.DataFrame({
        "symbol": ["RELIANCE"] * 5 + ["TCS"] * 4 + ["PENNY"] * 2,
        "date": [date(2023, 1, i) for i in range(1, 6)] + 
                [date(2023, 1, i) for i in range(1, 5)] + 
                [date(2023, 1, i) for i in range(1, 3)],
        "close": [100.0] * 5 + [30.0] * 4 + [10.0] * 2,
        "volume": [1000.0] * 5 + [500.0] * 4 + [10000.0] * 2
    })
    
    # RELIANCE: val = 100,000. coverage = 5/5 = 1.0. price = 100 -> tier_1
    # TCS: val = 15,000. coverage = 4/5 = 0.8. price = 30 -> tier_2
    # PENNY: val = 100,000. coverage = 2/5 = 0.4. price = 10 -> fail
    
    universe = builder.build_daily_universe(date(2023, 1, 5), ohlcv, lookback_days=5)
    
    assert len(universe) == 2
    
    rel_tier = universe.filter(pl.col("symbol") == "RELIANCE")["tier"][0]
    tcs_tier = universe.filter(pl.col("symbol") == "TCS")["tier"][0]
    
    assert rel_tier == "tier_1"
    assert tcs_tier == "tier_2"
    assert "PENNY" not in universe["symbol"].to_list()
