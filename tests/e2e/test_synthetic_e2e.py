import pytest
import polars as pl
from datetime import date, timedelta
from equity_engine.features.calculator import FeatureCalculator
from equity_engine.corporate_actions.adjustor import CorporateActionAdjustor
from equity_engine.universe.builder import UniverseBuilder
from equity_engine.regime.classifier import RegimeClassifier
from equity_engine.setups.breakout import BreakoutDetector
from equity_engine.outcomes.engine import OutcomeEngine
from equity_engine.backtest.controls import ControlEngine

def test_synthetic_e2e():
    # 1. Data Generation (300 days, 2 instruments)
    dates = [date(2023, 1, 1) + timedelta(days=i) for i in range(300)]
    df_inst1 = pl.DataFrame({
        "symbol": ["INST-1"] * 300,
        "date": dates,
        "open": [100.0 + i for i in range(300)], # Trends up
        "high": [105.0 + i for i in range(300)],
        "low": [95.0 + i for i in range(300)],
        "close": [102.0 + i for i in range(300)],
        "volume": [1000.0] * 300
    })
    
    df_inst2 = pl.DataFrame({
        "symbol": ["INST-2"] * 300,
        "date": dates,
        "open": [100.0] * 300, # Flat
        "high": [101.0] * 300,
        "low": [99.0] * 300,
        "close": [100.0] * 300,
        "volume": [1000.0] * 300
    })
    
    raw_df = pl.concat([df_inst1, df_inst2]).with_columns(pl.col("symbol").alias("instrument_id"))
    
    # 2. Corporate Actions (Split 2:1 on INST-1 at day 50)
    ca_df = pl.DataFrame({
        "date": [dates[50]],
        "factor": [2.0]
    })
    adj_inst1 = CorporateActionAdjustor.adjust_ohlcv(df_inst1, ca_df)
    adj_inst2 = CorporateActionAdjustor.adjust_ohlcv(df_inst2, pl.DataFrame())
    
    # 3. Features
    feat_inst1 = FeatureCalculator.calculate_features(adj_inst1)
    feat_inst2 = FeatureCalculator.calculate_features(adj_inst2)
    
    # 4. Universe (Evaluate at day 90)
    builder = UniverseBuilder({
        "liquidity_tiers": {
            "tier_1": {"min_median_traded_value": 0, "min_trading_days_coverage": 0, "min_price": 0}
        }
    })
    universe_90 = builder.build_daily_universe(dates[90], pl.concat([adj_inst1, adj_inst2]))
    assert len(universe_90) == 2
    
    # 5. Regime
    classifier = RegimeClassifier({"regimes": {"UPTREND": {"nifty_above_200_dma": False}}})
    nifty = pl.DataFrame({"date": dates, "close": [100.0]*300})
    regime = classifier.classify_regime(nifty)
    assert regime.value in ["UPTREND", "NEUTRAL", "RISK_OFF"]
    
    # 6. Detection
    detector = BreakoutDetector({"parameters": {"lookback_days": 252, "min_volume_relative": 0.0, "close_near_high_pct": 0.5}})
    events = detector.detect("INST-1", feat_inst1)
    # We should have some events detected because min_vol=0 and close is always near high in our trending synthetic data
    assert len(events) > 0
    
    # 7. Outcomes
    engine = OutcomeEngine({"timeout_days": 5, "watch_expiry_days": 2})
    outcomes = []
    for e in events:
        out = engine.evaluate_event(e, feat_inst1)
        if out["final_state"] == "COMPLETED":
            outcomes.append(out)
            
    # 8. Controls
    if outcomes:
        out_df = pl.DataFrame(outcomes)
        metrics = ControlEngine.calculate_metrics(out_df, [0.0]*len(outcomes))
        assert "mean_r" in metrics
