import pytest
import polars as pl
from datetime import date
from equity_engine.backtest.controls import ControlEngine

def test_control_metrics():
    outcomes = pl.DataFrame({
        "net_realized_r": [1.0, 2.0, -1.0, -1.0, 0.5],
        "detection_date": [date(2023, 1, 1)] * 5
    })
    
    # baseline_r_values = [0.0, 0.0, 0.0]
    metrics = ControlEngine.calculate_metrics(outcomes, baseline_r_values=[0.0])
    
    assert metrics["effective_n"] == 5
    assert metrics["mean_r"] == 0.3
    assert metrics["win_rate"] == 3 / 5
    assert metrics["baseline_mean_r"] == 0.0
    assert metrics["lift"] == 0.3
    
    assert metrics["ci_lower"] <= metrics["mean_r"]
    assert metrics["ci_upper"] >= metrics["mean_r"]
    
def test_control_metrics_empty():
    outcomes = pl.DataFrame({"net_realized_r": []})
    metrics = ControlEngine.calculate_metrics(outcomes)
    assert metrics == {}
