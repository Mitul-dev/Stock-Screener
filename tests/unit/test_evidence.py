import pytest
import polars as pl
from datetime import date
from equity_engine.evidence.snapshot import EvidenceSnapshot

def test_evidence_snapshot(tmp_path):
    manager = EvidenceSnapshot(str(tmp_path))
    
    outcomes = pl.DataFrame({
        "event_id": ["E1", "E2"],
        "realized_r": [1.0, -1.0]
    })
    
    stats = {"mean_r": 0.0, "win_rate": 0.5}
    
    snap_id = manager.create_snapshot(
        setup_version="BREAKOUT_V1",
        universe_version="V1",
        methodology_version="V1",
        data_cutoff=date(2023, 1, 1),
        statistics=stats,
        outcomes_df=outcomes
    )
    
    assert snap_id is not None
    
    meta, loaded_df = manager.load_snapshot(snap_id)
    
    assert meta["setup_version"] == "BREAKOUT_V1"
    assert meta["statistics"]["mean_r"] == 0.0
    assert len(loaded_df) == 2
    assert loaded_df["event_id"][0] == "E1"
