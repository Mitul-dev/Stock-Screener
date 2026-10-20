import pytest
import polars as pl
from datetime import date, timedelta
from equity_engine.regime.classifier import RegimeClassifier, MarketRegimeState

def test_regime_classifier():
    config = {
        "regimes": {
            "UPTREND": {
                "nifty_above_200_dma": True,
                "breadth_pct_above_50_dma_min": 0.50
            },
            "RISK_OFF": {
                "vix_min": 25.0,
                "nifty_below_200_dma": True
            }
        }
    }
    
    classifier = RegimeClassifier(config)
    
    dates = [date(2023, 1, 1) + timedelta(days=i) for i in range(250)]
    
    # Uptrend scenario: Nifty > 200 SMA (which means price > avg), breadth > 0.5, VIX < 25
    nifty = pl.DataFrame({
        "date": dates,
        "close": [100.0 + i for i in range(250)] # End at 349. 200dma will be ~ (349+150)/2 = 249. 349 > 249 -> above 200dma
    })
    
    breadth = pl.DataFrame({
        "date": [dates[-1]],
        "pct_above_50_dma": [0.60]
    })
    
    vix = pl.DataFrame({
        "date": [dates[-1]],
        "close": [15.0]
    })
    
    regime = classifier.classify_regime(nifty, breadth, vix)
    assert regime == MarketRegimeState.UPTREND
    
    # Neutral scenario: breadth < 0.5
    breadth_neutral = pl.DataFrame({
        "date": [dates[-1]],
        "pct_above_50_dma": [0.40]
    })
    regime = classifier.classify_regime(nifty, breadth_neutral, vix)
    assert regime == MarketRegimeState.NEUTRAL
    
    # Risk off scenario: VIX >= 25
    vix_high = pl.DataFrame({
        "date": [dates[-1]],
        "close": [30.0]
    })
    regime = classifier.classify_regime(nifty, breadth, vix_high)
    assert regime == MarketRegimeState.RISK_OFF
