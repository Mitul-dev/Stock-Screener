"""Acceptance checks for partition provenance and frozen evidence integrity."""

from datetime import date, timedelta
import hashlib

import polars as pl
import pytest

from equity_engine.backtest.controls import ControlEngine
from equity_engine.backtest.engine import empty_outcomes
from equity_engine.evidence.snapshot import EvidenceSnapshot


START = date(2020, 1, 1)
CUTOFF = START + timedelta(days=30)


def outcomes():
    return pl.DataFrame({
        "event_id": [f"event-{i}" for i in range(6)],
        "setup": ["BREAKOUT_V1.0"] * 6,
        "detection_date": [START + timedelta(days=i) for i in range(6)],
        "exit_date": [START + timedelta(days=i + 3) for i in range(6)],
        "net_realized_r": [0.5, 0.8, 1.1, 1.4, 1.7, 2.0],
        "partition": ["holdout"] * 6,
        "is_oos": [True] * 6,
    })


def freeze(manager, frame, **kwargs):
    return manager.create_snapshot(
        "BREAKOUT_V1.0", "V1", "V1", CUTOFF,
        {"status": "INSUFFICIENT EVIDENCE"}, frame,
        partition="holdout", **kwargs,
    )


def test_metrics_reject_a_mixture_of_discovery_and_holdout():
    mixed = outcomes().with_columns(
        pl.when(pl.col("event_id") == "event-0")
        .then(pl.lit("discovery")).otherwise(pl.col("partition")).alias("partition")
    )
    with pytest.raises(ValueError, match="partition"):
        ControlEngine.calculate_metrics(mixed)


def test_one_oos_row_cannot_validate_other_in_sample_rows():
    mixed_flags = outcomes().with_columns(
        (pl.col("event_id") == "event-0").alias("is_oos")
    )
    metrics = ControlEngine.calculate_metrics(mixed_flags)
    assert metrics["effective_n"] == 6
    assert metrics["distinct_time_blocks"] == 6
    assert metrics["ci_lower"] > 0
    assert metrics["status"] == "INSUFFICIENT EVIDENCE"


def test_discovery_label_cannot_be_overridden_by_true_oos_flags():
    discovery = outcomes().with_columns(pl.lit("discovery").alias("partition"))
    metrics = ControlEngine.calculate_metrics(discovery, is_oos=True)
    assert metrics["ci_lower"] > 0
    assert metrics["status"] == "INSUFFICIENT EVIDENCE"


def test_pure_holdout_analysis_remains_deterministic_under_existing_statistical_rule():
    first = ControlEngine.calculate_metrics(outcomes(), seed=71)
    second = ControlEngine.calculate_metrics(outcomes(), seed=71)
    assert first == second
    assert first["status"] == "VALIDATED"
    assert first["baseline_type"] == "STATIC"
    assert first["distinct_time_blocks"] == 6
    assert first["dependence_limitation"]


def test_empty_snapshot_has_a_real_hashed_parquet_file_and_preserves_its_schema(tmp_path):
    manager = EvidenceSnapshot(str(tmp_path))
    frame = empty_outcomes()
    identity = freeze(manager, frame)
    outcomes_path = manager.snapshots_dir / f"{identity}_outcomes.parquet"
    assert outcomes_path.is_file()
    metadata, loaded = manager.load_snapshot(identity)
    assert loaded.is_empty()
    assert loaded.schema == frame.schema
    assert metadata["outcomes_count"] == 0
    assert metadata["output_hash"] == hashlib.sha256(outcomes_path.read_bytes()).hexdigest()


def test_missing_outcomes_file_fails_instead_of_returning_empty_evidence(tmp_path):
    manager = EvidenceSnapshot(str(tmp_path))
    identity = freeze(manager, outcomes())
    (manager.snapshots_dir / f"{identity}_outcomes.parquet").unlink()
    with pytest.raises(FileNotFoundError, match="outcomes"):
        manager.load_snapshot(identity)


def test_modified_valid_parquet_fails_frozen_evidence_hash_verification(tmp_path):
    manager = EvidenceSnapshot(str(tmp_path))
    identity = freeze(manager, outcomes())
    changed = outcomes().with_columns((pl.col("net_realized_r") + 1).alias("net_realized_r"))
    changed.write_parquet(manager.snapshots_dir / f"{identity}_outcomes.parquet")
    with pytest.raises(ValueError, match="integrity|hash"):
        manager.load_snapshot(identity)


def test_snapshot_rejects_an_exit_after_its_declared_data_cutoff(tmp_path):
    manager = EvidenceSnapshot(str(tmp_path))
    future_exit = outcomes().with_columns(
        pl.lit(CUTOFF + timedelta(days=1)).alias("exit_date")
    )
    with pytest.raises(ValueError, match="cutoff"):
        freeze(manager, future_exit)
    assert list(manager.snapshots_dir.iterdir()) == []


def test_snapshot_rejects_rows_from_another_partition(tmp_path):
    manager = EvidenceSnapshot(str(tmp_path))
    mixed = outcomes().with_columns(
        pl.when(pl.col("event_id") == "event-0")
        .then(pl.lit("validation")).otherwise(pl.col("partition")).alias("partition")
    )
    with pytest.raises(ValueError, match="partition"):
        freeze(manager, mixed)
    assert list(manager.snapshots_dir.iterdir()) == []


def test_reusing_a_snapshot_identity_cannot_overwrite_existing_evidence(tmp_path):
    manager = EvidenceSnapshot(str(tmp_path))
    identity = freeze(manager, outcomes(), snapshot_id="frozen-holdout")
    paths = [manager.snapshots_dir / f"{identity}_{suffix}" for suffix in ("meta.json", "outcomes.parquet")]
    before = [path.read_bytes() for path in paths]
    changed = outcomes().with_columns((pl.col("net_realized_r") + 1).alias("net_realized_r"))
    with pytest.raises(FileExistsError):
        freeze(manager, changed, snapshot_id=identity)
    assert [path.read_bytes() for path in paths] == before
