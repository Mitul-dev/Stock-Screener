"""Consumers exercise actual production artifacts, frozen bytes and Streamlit."""

from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
from unittest.mock import Mock

import polars as pl
import pytest
from streamlit.testing.v1 import AppTest

from equity_engine.alerts.telegram import TelegramAlerter
from equity_engine.corporate_actions.adjustor import CorporateActionAdjustor
from equity_engine.evidence.run import RunEvidence, RunIntegrityError
from equity_engine.ingestion.quality import assess_quality
from tests.integration.test_pilot_pipeline import ROOT, _write_inputs, production_module


@pytest.fixture(scope="module")
def consumer_pilot(tmp_path_factory, production_module):
    folder = tmp_path_factory.mktemp("consumer_pilot")
    options, _ = _write_inputs(folder / "inputs")
    return production_module.run_pilot(output_dir=folder / "runs", **options)


@pytest.fixture
def manifest_path(tmp_path, consumer_pilot):
    folder = tmp_path / "moved_run"
    shutil.copytree(consumer_pilot["run_dir"], folder)
    return folder / "manifest.json"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    # Populated credentials must not make default previews deliver.
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "mock-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "mock-chat")
    monkeypatch.setattr("requests.post", Mock(side_effect=AssertionError("No real delivery allowed")))


def read(path):
    return json.loads(Path(path).read_bytes())


def write_manifest(path, manifest):
    payload = json.dumps(manifest, indent=2, sort_keys=True).encode()
    path.write_bytes(payload)
    path.with_name("manifest.sha256").write_text(hashlib.sha256(payload).hexdigest() + "\n")


def change_metadata(path, entry, changes):
    target = path.parent / entry["metadata"]["relative_path"]
    metadata = read(target)
    metadata.update(changes)
    target.write_text(json.dumps(metadata))
    entry["metadata"]["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()


def alert_event(run, partition="validation"):
    return run.frames["events"].filter(
        (pl.col("partition") == partition) & pl.col("universe_eligible") &
        (pl.col("setup") == "BREAKOUT_V1.0")).row(0, named=True)


def send(alerter, path, event, **kwargs):
    return alerter.send_alert(event["event_id"], event["instrument_id"], event["setup"],
        "Local research candidate", manifest_path=path, event_time=event["detection_date"], **kwargs)


def dashboard(path):
    from equity_engine.dashboard.app import render_overview
    render_overview(path)


def test_quality_is_persisted_bound_to_inputs_and_never_claims_source_certification(manifest_path):
    run = RunEvidence(manifest_path)
    quality = run.quality
    assert run.quality_status == "PASSED_WITH_WARNINGS"
    assert quality["trial_id"] == run.manifest["trial_id"]
    assert quality["input_hash"] == run.manifest["input_hash"]
    checks = {check["name"]: check for check in quality["checks"]}
    assert checks["ohlcv"]["status"] == "PASSED"
    assert checks["observed_session_coverage"]["counts"]["missing_instrument_sessions"] == 20
    assert checks["delivery_availability"]["counts"]["rows_without_delivery"] > 0
    assert checks["delivery_availability"]["status"] == "UNAVAILABLE"
    assert checks["calendar_completeness"]["status"] == "UNAVAILABLE"
    assert checks["corporate_action_reconciliation"]["status"] == "UNAVAILABLE"
    assert checks["identifier_history"]["status"] == "UNAVAILABLE"
    assert not quality["paper_research_approved"]
    assert run.frames["features"]["deliverable_quantity"].null_count() == run.frames["features"].height
    assert all(metadata["quality_sha256"] == run.manifest["outputs"]["quality"]["sha256"]
               for metadata, _ in run.snapshots.values())


def test_moved_run_uses_relative_artifacts_without_rewriting_frozen_metadata(manifest_path):
    run = RunEvidence(manifest_path)
    assert run.root != Path(run.manifest["run_dir"])
    assert len(run.snapshots) == 6
    assert run.frames["outcomes"].height == 8


def test_dashboard_renders_actual_run_quality_partitions_sources_and_frozen_files(manifest_path):
    app = AppTest.from_function(dashboard, args=(str(manifest_path),)).run(timeout=10)
    assert not app.exception
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Data Quality"] == "PASSED_WITH_WARNINGS"
    assert metrics["Detected Setups"] == "11"
    assert len(app.dataframe) == 5
    assert "paper research is not approved" in app.warning[0].value


def test_dashboard_selects_a_current_manifest_from_the_runs_folder(manifest_path, monkeypatch):
    folder = manifest_path.parent.parent / "data/processed/pilot_runs/run-one"
    folder.parent.mkdir(parents=True)
    shutil.copytree(manifest_path.parent, folder)
    monkeypatch.chdir(manifest_path.parent.parent)
    app = AppTest.from_file(ROOT / "src/equity_engine/dashboard/app.py").run(timeout=10)
    assert not app.exception
    assert app.sidebar.selectbox[0].label == "Run"
    assert app.sidebar.selectbox[0].options == ["run-one"]
    assert any(metric.label == "Data Quality" and metric.value == "PASSED_WITH_WARNINGS"
               for metric in app.metric)


@pytest.mark.parametrize("missing_declaration", [False, True])
def test_absent_quality_is_unavailable_and_cannot_be_inferred_from_nonempty_outcomes(
        manifest_path, tmp_path, missing_declaration):
    manifest = read(manifest_path)
    if missing_declaration:
        manifest["outputs"].pop("quality")
        write_manifest(manifest_path, manifest)
    else:
        (manifest_path.parent / "quality.json").unlink()
    run = RunEvidence(manifest_path)
    assert run.frames["outcomes"].height > 0
    assert run.quality_status == "UNAVAILABLE"
    app = AppTest.from_function(dashboard, args=(str(manifest_path),)).run(timeout=10)
    assert not app.exception
    assert any(metric.label == "Data Quality" and metric.value == "UNAVAILABLE" for metric in app.metric)
    alerter = TelegramAlerter(str(tmp_path / "alerts.sqlite"))
    try:
        assert not send(alerter, manifest_path, alert_event(run))
        assert "quality" in alerter.last_error
    finally:
        alerter.conn.close()


@pytest.mark.parametrize("artifact", ["manifest", "quality", "features", "universe", "regime", "events", "outcomes", "statistics", "snapshot_meta", "snapshot_outcomes"])
@pytest.mark.parametrize("corrupt", [False, True])
def test_missing_or_corrupt_artifacts_block_consumers(manifest_path, tmp_path, artifact, corrupt):
    run = RunEvidence(manifest_path)
    event = alert_event(run)
    manifest = run.manifest
    if artifact == "manifest":
        target = manifest_path
    elif artifact.startswith("snapshot"):
        field = "metadata" if artifact == "snapshot_meta" else "outcomes"
        target = manifest_path.parent / manifest["snapshots"][0][field]["relative_path"]
    else:
        target = manifest_path.parent / manifest["outputs"][artifact]["relative_path"]
    if corrupt:
        target.write_bytes(target.read_bytes() + b"tampered")
    else:
        target.unlink()
    if not corrupt and artifact == "quality":
        assert RunEvidence(manifest_path).quality_status == "UNAVAILABLE"
    else:
        with pytest.raises((OSError, ValueError)):
            RunEvidence(manifest_path)
    alerter = TelegramAlerter(str(tmp_path / "alerts.sqlite"))
    try:
        assert not send(alerter, manifest_path, event)
        assert alerter.conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0
    finally:
        alerter.conn.close()
    app = AppTest.from_function(dashboard, args=(str(manifest_path),)).run(timeout=10)
    assert not app.exception
    assert any(metric.value in {"FAILED", "UNAVAILABLE"} for metric in app.metric if metric.label == "Data Quality")


@pytest.mark.parametrize("changes", [
    {"trial_id": "another-run"}, {"setup_version": "VCB_V1.0"},
    {"setup_version": "BREAKOUT_V99"}, {"input_hash": "0" * 64},
    {"quality_sha256": "0" * 64}, {"data_cutoff": "2099-01-01"},
    {"partition": "holdout"},
])
def test_semantic_snapshot_mismatches_fail_even_when_artifact_hash_is_updated(manifest_path, changes):
    manifest = read(manifest_path)
    change_metadata(manifest_path, manifest["snapshots"][0], changes)
    write_manifest(manifest_path, manifest)
    with pytest.raises(RunIntegrityError, match="mismatch"):
        RunEvidence(manifest_path)


def test_quality_from_another_run_cannot_authorize_this_run(manifest_path):
    manifest = read(manifest_path)
    quality_path = manifest_path.parent / "quality.json"
    quality = read(quality_path)
    quality["trial_id"] = "another-run"
    quality_path.write_text(json.dumps(quality))
    manifest["outputs"]["quality"]["sha256"] = hashlib.sha256(quality_path.read_bytes()).hexdigest()
    write_manifest(manifest_path, manifest)
    with pytest.raises(RunIntegrityError, match="Quality/run"):
        RunEvidence(manifest_path)


def test_artifact_paths_cannot_escape_the_selected_run(manifest_path):
    manifest = read(manifest_path)
    manifest["outputs"]["outcomes"]["relative_path"] = "../other/outcomes.parquet"
    write_manifest(manifest_path, manifest)
    with pytest.raises(RunIntegrityError, match="path"):
        RunEvidence(manifest_path)


def test_input_list_mismatch_and_unavailable_critical_checks_cannot_authorize_evidence(manifest_path):
    manifest = read(manifest_path)
    manifest["inputs"][0]["sha256"] = "0" * 64
    write_manifest(manifest_path, manifest)
    with pytest.raises(RunIntegrityError, match="input hash"):
        RunEvidence(manifest_path)


def test_quality_cannot_silently_skip_a_critical_check(manifest_path):
    manifest = read(manifest_path)
    path = manifest_path.parent / "quality.json"
    quality = read(path)
    next(check for check in quality["checks"] if check["name"] == "ohlcv")["status"] = "UNAVAILABLE"
    path.write_text(json.dumps(quality))
    manifest["outputs"]["quality"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_manifest(manifest_path, manifest)
    with pytest.raises(RunIntegrityError, match="Critical quality"):
        RunEvidence(manifest_path)


def test_default_dry_run_selects_earlier_matching_evidence_and_is_idempotent(manifest_path, tmp_path):
    run = RunEvidence(manifest_path)
    event = alert_event(run)
    alerter = TelegramAlerter(str(tmp_path / "alerts.sqlite"))
    try:
        assert send(alerter, manifest_path, event)
        assert send(alerter, manifest_path, event)
        rows = alerter.conn.execute("SELECT event_id, snapshot_id, delivery_mode, message FROM outbox").fetchall()
        assert len(rows) == 1
        event_id, snapshot_id, mode, message = rows[0]
        assert event_id == event["event_id"] and event_id != snapshot_id
        assert mode == "DRY_RUN"
        metadata = run.snapshots[snapshot_id][0]
        assert metadata["partition"] == "discovery"
        assert metadata["setup_version"] == event["setup"]
        assert date.fromisoformat(metadata["data_cutoff"]) < event["detection_date"]
        assert "Paper research is not approved" in message and "Quality limitation" in message
        import requests
        requests.post.assert_not_called()
    finally:
        alerter.conn.close()


@pytest.mark.parametrize("field,value", [
    ("instrument_id", "wrong-instrument"), ("setup", "VCB_V1.0"),
    ("setup", "BREAKOUT_V99"), ("event_id", "absent-event"),
    ("detection_date", date(2099, 1, 1)),
])
def test_alert_rejects_event_identity_version_or_time_mismatch(manifest_path, tmp_path, field, value):
    event = alert_event(RunEvidence(manifest_path))
    event[field] = value
    alerter = TelegramAlerter(str(tmp_path / "alerts.sqlite"))
    try:
        assert not send(alerter, manifest_path, event)
        assert alerter.conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0
    finally:
        alerter.conn.close()


def test_future_evidence_and_universe_excluded_events_are_rejected(manifest_path, tmp_path):
    run = RunEvidence(manifest_path)
    event = alert_event(run)
    future = next(identity for identity, (metadata, _) in run.snapshots.items()
                  if metadata["partition"] == "holdout" and metadata["setup_version"] == event["setup"])
    alerter = TelegramAlerter(str(tmp_path / "alerts.sqlite"))
    try:
        assert not send(alerter, manifest_path, event, snapshot_id=future)
        assert "before the event" in alerter.last_error
        excluded = run.frames["events"].filter(~pl.col("universe_eligible")).row(0, named=True)
        assert not send(alerter, manifest_path, excluded)
        assert not send(alerter, manifest_path, alert_event(run, "discovery"))
    finally:
        alerter.conn.close()


def test_repeat_alert_reverifies_evidence_and_dry_run_cannot_suppress_mocked_delivery(manifest_path, tmp_path, monkeypatch):
    run = RunEvidence(manifest_path)
    event = alert_event(run)
    post = Mock(return_value=Mock(status_code=200, json=Mock(return_value={"ok": True})))
    monkeypatch.setattr("requests.post", post)
    alerter = TelegramAlerter(str(tmp_path / "alerts.sqlite"))
    try:
        assert send(alerter, manifest_path, event)
        assert send(alerter, manifest_path, event, dry_run=False)
        assert send(alerter, manifest_path, event, dry_run=False)
        assert post.call_count == 1
        assert alerter.conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 2
        (manifest_path.parent / "quality.json").write_text("corrupt")
        assert not send(alerter, manifest_path, event)
        assert post.call_count == 1
    finally:
        alerter.conn.close()


def test_legacy_outbox_rows_survive_schema_migration(tmp_path):
    path = tmp_path / "alerts.sqlite"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE outbox (alert_id TEXT PRIMARY KEY, instrument_id TEXT, setup TEXT, message TEXT, sent_at TIMESTAMP)")
        conn.execute("INSERT INTO outbox VALUES ('legacy', 'source-id', 'setup', 'preserved', '2026-10-01')")
    alerter = TelegramAlerter(str(path))
    try:
        assert alerter.conn.execute("SELECT message FROM outbox WHERE alert_id='legacy'").fetchone()[0] == "preserved"
    finally:
        alerter.conn.close()


@pytest.mark.parametrize("issue", ["missing_cohort", "missing_session", "abnormal_return"])
def test_critical_quality_failures_are_persisted_and_withhold_all_evidence(tmp_path, production_module, issue):
    options, dates = _write_inputs(tmp_path / "inputs")
    if issue == "missing_cohort":
        options["cohort"] = ["BREAKOUT", "MISSING"]
    elif issue == "missing_session":
        calendar_path = tmp_path / "calendar.csv"
        pl.DataFrame({"date": dates}).write_csv(calendar_path)
        options["calendar_path"] = calendar_path
        source = pl.read_csv(options["input_path"])
        source.filter(pl.col("TradDt") != dates[700].isoformat()).write_csv(options["input_path"])
    else:
        source = pl.read_csv(options["input_path"])
        source.with_columns([
            pl.when(pl.col("TradDt") >= dates[900].isoformat()).then(pl.col(column) * 2)
            .otherwise(pl.col(column)).alias(column)
            for column in ["OpnPric", "HghPric", "LwPric", "ClsPric"]
        ]).write_csv(options["input_path"])
    manifest = production_module.run_pilot(output_dir=tmp_path / "runs", **options)
    run = RunEvidence(manifest["manifest_path"])
    assert run.quality_status == "FAILED"
    assert not run.quality["evidence_allowed"]
    assert manifest["status"] == "DATA QUALITY FAILED"
    assert manifest["snapshots"] == []
    assert run.frames["outcomes"].height > 0
    assert not run.frames["outcomes"]["evidence_eligible"].any()
    assert run.frames["outcomes"]["evidence_withheld_reason"].unique().to_list() == ["DATA_QUALITY_FAILED"]
    assert not manifest["paper_research_approved"]
    alerter = TelegramAlerter(str(tmp_path / "alerts.sqlite"))
    try:
        assert not send(alerter, manifest["manifest_path"], alert_event(run))
    finally:
        alerter.conn.close()
    app = AppTest.from_function(dashboard, args=(manifest["manifest_path"],)).run(timeout=10)
    assert not app.exception
    assert any(metric.label == "Data Quality" and metric.value == "FAILED" for metric in app.metric)


def test_no_event_run_and_matching_calendar_are_valid_engineering_inputs(tmp_path, production_module):
    options, dates = _write_inputs(tmp_path / "quiet", quiet=True)
    calendar_path = tmp_path / "calendar.csv"
    pl.DataFrame({"date": dates}).write_csv(calendar_path)
    manifest = production_module.run_pilot(output_dir=tmp_path / "runs", calendar_path=calendar_path, **options)
    run = RunEvidence(manifest["manifest_path"])
    assert run.quality["evidence_allowed"]
    assert run.frames["events"].is_empty()
    assert run.snapshots and all(frozen.is_empty() for _, frozen in run.snapshots.values())
    assert manifest["status"] == "INSUFFICIENT EVIDENCE"
    assert next(check for check in run.quality["checks"] if check["name"] == "calendar_completeness")["status"] == "PASSED"
    app = AppTest.from_function(dashboard, args=(manifest["manifest_path"],)).run(timeout=10)
    assert not app.exception
    assert any(metric.label == "Data Quality" and metric.value == "PASSED_WITH_WARNINGS" for metric in app.metric)


def test_quality_distinguishes_applied_split_from_unexplained_return_and_records_staleness(manifest_path):
    run = RunEvidence(manifest_path)
    raw = run.frames["features"].filter(pl.col("symbol") == "BREAKOUT").head(10)
    raw = raw.with_columns([
        pl.when(pl.col("date") >= raw["date"][5]).then(pl.col(column) / 2)
        .otherwise(pl.col(column)).alias(column) for column in ["open", "high", "low", "close"]])
    raw = raw.drop([column for column in raw.columns if column.startswith("adj_") or column == "price_basis"])
    actions = pl.DataFrame({"date": [raw["date"][5]], "factor": [2.0]})
    adjusted = CorporateActionAdjustor.adjust_ohlcv(raw, actions)
    report = assess_quality(raw, adjusted, run.manifest["inputs"])
    assert next(c for c in report["checks"] if c["name"] == "abnormal_adjusted_returns")["status"] == "PASSED"
    unadjusted = CorporateActionAdjustor.adjust_ohlcv(raw, actions.head(0))
    report = assess_quality(raw, unadjusted, run.manifest["inputs"])
    assert next(c for c in report["checks"] if c["name"] == "abnormal_adjusted_returns")["status"] == "FAILED"
    # An instrument with no bars on the last two observed sessions is stale.
    early = raw.head(8).with_columns(pl.lit("early-id").alias("instrument_id"), pl.lit("EARLY").alias("symbol"))
    expanded = pl.concat([raw, early])
    report = assess_quality(expanded, expanded.with_columns(pl.lit(100.0).alias("adj_close")), run.manifest["inputs"])
    stale = next(c for c in report["checks"] if c["name"] == "stale_history")
    assert stale["status"] == "WARNING" and stale["examples"][0]["lag_sessions"] == 2


def test_quality_flags_source_dates_and_concurrent_symbol_identities(manifest_path):
    run = RunEvidence(manifest_path)
    raw = run.frames["features"].filter(pl.col("symbol") == "BREAKOUT").head(10)
    collision = raw.with_columns(pl.lit("different-id").alias("instrument_id"))
    combined = pl.concat([raw, collision])
    report = assess_quality(combined, combined, run.manifest["inputs"])
    check = next(check for check in report["checks"] if check["name"] == "identifier_collisions")
    assert check["status"] == "FAILED" and check["counts"]["ambiguous_symbol_dates"] == 10
    changed = raw.with_columns(pl.lit("1999-01-01").alias("source_date"))
    report = assess_quality(changed, changed, run.manifest["inputs"])
    assert next(check for check in report["checks"] if check["name"] == "source_identity")["status"] == "FAILED"


def test_original_legacy_run_contract_is_not_mistaken_for_current_quality(tmp_path):
    source = next((ROOT / "research/reports/production_acceptance_2026-10-20/synthetic_runs").glob("*/manifest.json"))
    shutil.copytree(source.parent, tmp_path / "legacy")
    with pytest.raises(RunIntegrityError, match="Legacy.*unavailable"):
        RunEvidence(tmp_path / "legacy/manifest.json")


def test_preview_command_prepares_only_local_run_bound_alerts(manifest_path, tmp_path):
    spec = importlib.util.spec_from_file_location("preview_run_alerts", ROOT / "scripts/preview_run_alerts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    outbox = tmp_path / "preview.sqlite"
    results = module.preview(manifest_path, outbox_path=outbox)
    assert len(results) == 11
    assert sum(row["dry_run_prepared"] for row in results) == 4
    with sqlite3.connect(outbox) as conn:
        assert conn.execute("SELECT DISTINCT delivery_mode FROM outbox").fetchall() == [("DRY_RUN",)]
    import requests
    requests.post.assert_not_called()
