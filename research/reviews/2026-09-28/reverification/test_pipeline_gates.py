"""Independent gate probes. Synthetic files are NOT official-data fixtures.

All writes are to pytest temporary directories or this review directory.
Existing source, strategy configuration, raw files and old reports are preserved.
"""
from collections import Counter
from datetime import date, timedelta
import json
from pathlib import Path
import runpy
from unittest.mock import patch
import zipfile

import polars as pl
import pytest
import yaml
from polars.testing import assert_frame_equal

from equity_engine.ingestion.nse_importer import NSEImporter
from equity_engine.corporate_actions.adjustor import CorporateActionAdjustor
from equity_engine.features.calculator import FeatureCalculator
from equity_engine.setups.breakout import BreakoutDetector, SetupEvent
from equity_engine.setups.vcb import VCBDetector
from equity_engine.outcomes.engine import OutcomeEngine
from equity_engine.backtest.engine import ResearchEngine
from equity_engine.backtest.controls import ControlEngine
from equity_engine.evidence.snapshot import EvidenceSnapshot
from equity_engine.alerts.telegram import TelegramAlerter

ROOT = Path(__file__).resolve().parents[4]
DEST = Path(__file__).resolve().parent
CONFIG = yaml.safe_load((ROOT / "config/setups.yaml").read_text())["setups"]


def sessions(n):
    result, day = [], date(2020, 1, 1)
    while len(result) < n:
        if day.weekday() < 5:
            result.append(day)
        day += timedelta(days=1)
    return result


def source_frame(symbol="SYNTHETIC", n=340):
    dates = sessions(n)
    rows = []
    for i, day in enumerate(dates):
        op, hi, lo, cl, vol = 100., 101., 99., 100., 1000
        if symbol in ("BREAKOUT", "INVALID"):
            if i == 260:
                vol = 2000
            elif i == 261:
                op, hi, lo, cl = 101., 103., 100., 102.
            elif i >= 262:
                op, hi, lo, cl = 103., 104., 102., 103.
                if symbol == "INVALID":
                    op, hi, lo, cl = 90., 91., 88., 89.
        elif symbol == "EXPIRED" and i == 260:
            vol = 2000
        elif symbol == "FAILED":
            if i == 260:
                vol = 2000
            elif i == 261:
                op, hi, lo, cl = 101., 103., 100., 102.
            elif i >= 262:
                # Hits stop loss (low goes to 95)
                op, hi, lo, cl = 101., 102., 95., 96.
        elif symbol == "CENSORED" and i == n - 1:
            vol = 2000
        elif symbol == "VCB":
            if i < 200:
                hi, lo = 110., 90.
            elif i < 260:
                hi, lo = 100.5, 99.5
            elif i == 260:
                op, hi, lo, cl, vol = 100., 101., 100., 100.75, 2000
            else:
                op, hi, lo, cl = 101., 102., 100.75, 101.
        rows.append({"TradDt": day.isoformat(), "ISIN": f"TEST_{symbol}",
                     "TckrSymb": symbol, "SctySrs": "EQ", "OpnPric": op,
                     "HghPric": hi, "LwPric": lo, "ClsPric": cl,
                     "TtlTradgVol": vol, "TtlTrfVal": float(vol) * cl})
    return pl.DataFrame(rows)


def raw_frame(symbol, n=340):
    # Use the real normalizer, not handwritten canonical feature columns.
    importer = NSEImporter.__new__(NSEImporter)
    return importer._parse_consolidated(source_frame(symbol, n))


@pytest.fixture(scope="module")
def chain(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("component_chain")
    frames, events = [], []
    stages = {}
    importer = NSEImporter(str(tmp), str(tmp / "processed"))
    for symbol in ["BREAKOUT", "EXPIRED", "CENSORED", "INVALID", "VCB", "FAILED"]:
        path = tmp / f"{symbol}.csv"
        source_frame(symbol).write_csv(path)
        raw = pl.read_parquet(importer.process_bhavcopy(str(path)))
        adjusted = CorporateActionAdjustor.adjust_ohlcv(raw, pl.DataFrame())
        features = FeatureCalculator.calculate_features(adjusted)
        frames.append(features)
        b_events = BreakoutDetector(CONFIG["BREAKOUT_V1"]).detect(f"TEST_{symbol}", features)
        v_events = VCBDetector(CONFIG["VCB_V1"]).detect(f"TEST_{symbol}", features)
        events.extend(b_events + v_events)
        if symbol == "BREAKOUT":
            event = next(e for e in b_events if e.timestamp == sessions(340)[260])
            engine = OutcomeEngine({})
            for label, end in [("watch", 260), ("confirmed", 261), ("completed", 300)]:
                stages[label] = engine.evaluate_event(event, features.head(end + 1))["final_state"]
    history = pl.concat(frames)
    outcomes = ResearchEngine(OutcomeEngine({})).run_backtest(events, history)
    completed = outcomes.filter(pl.col("final_state") == "COMPLETED")
    metrics = {}
    snapshots = {}
    manager = EvidenceSnapshot(str(tmp))
    for setup in completed["setup"].unique().sort().to_list():
        family = completed.filter(pl.col("setup") == setup)
        stats = ControlEngine.calculate_metrics(family, seed=42)
        metrics[setup] = stats
        snapshot_id = manager.create_snapshot(setup, "review-fixture-only", "review-probe",
                                              history["date"].max(), stats, family)
        metadata, loaded = manager.load_snapshot(snapshot_id)
        assert_frame_equal(loaded, family)
        snapshots[setup] = metadata
    summary = {"stages": stages, "events": len(events),
               "states": dict(Counter(outcomes["final_state"].to_list())),
               "completed_by_setup": completed.group_by("setup").len().sort("setup").to_dicts(),
               "metrics": metrics, "snapshots": snapshots,
               "note": "Review-assembled component chain, not proof that the production pilot calls research/snapshots."}
    (DEST / "component_chain.json").write_text(json.dumps(summary, indent=2))
    return {"outcomes": outcomes, "summary": summary}


def test_nonvacuous_component_chain_and_snapshot_roundtrip(chain):
    summary = chain["summary"]
    assert summary["stages"] == {"watch": "WATCH", "confirmed": "CONFIRMED", "completed": "COMPLETED"}
    assert summary["states"]["COMPLETED"] >= 2
    assert summary["states"]["EXPIRED"] >= 1
    assert summary["states"]["WATCH"] >= 1
    assert summary["states"]["INVALIDATED"] >= 1
    assert set(summary["metrics"]) == {"BREAKOUT_V1.0", "VCB_V1.0"}


def test_full_chain_has_failed_setup_state(chain):
    assert "FAILED" in chain["summary"]["states"], "Only EXPIRED/INVALIDATED are implemented for these failure paths; FAILED is not emitted."


def test_full_chain_has_both_target_touch_labels(chain):
    fields = [c.lower() for c in chain["outcomes"].columns]
    assert any("1r" in c for c in fields) and any("2r" in c for c in fields), fields


def test_snapshot_records_complete_trial_metadata(chain):
    required = {"configuration", "methodology_version", "universe_version", "cost_model",
                "date_boundaries", "input_hash", "random_seed", "output_hash"}
    metadata = next(iter(chain["summary"]["snapshots"].values()))
    assert required <= set(metadata), f"Missing trial fields: {sorted(required - set(metadata))}"


def test_bootstrap_is_deterministic_and_baseline_is_static(chain):
    outcomes = chain["outcomes"].filter((pl.col("final_state") == "COMPLETED") & (pl.col("setup") == "BREAKOUT_V1.0"))
    a = ControlEngine.calculate_metrics(outcomes, seed=123)
    b = ControlEngine.calculate_metrics(outcomes, seed=123)
    assert a == b
    assert a["baseline_type"] == "STATIC"


def test_statistics_report_dependence_limitations(chain):
    stats = next(iter(chain["summary"]["metrics"].values()))
    assert any("dependence" in key or "limitation" in key for key in stats), stats


def test_mixed_families_not_silently_pooled(chain):
    completed = chain["outcomes"].filter(pl.col("final_state") == "COMPLETED")
    assert completed["setup"].n_unique() == 2
    try:
        stats = ControlEngine.calculate_metrics(completed)
    except ValueError:
        return  # An explicit mixed-family rejection would be sufficient.
    assert "by_setup" in stats, "Two setup families silently returned as one aggregate."


def test_event_identity_is_deterministic():
    args = ("TEST_A", "BREAKOUT_V1.0", date(2020, 1, 1), 100., {"atr_14": 4.})
    assert SetupEvent(*args).event_id == SetupEvent(*args).event_id


def test_split_basis_is_consistent_through_detection_and_outcomes():
    raw = raw_frame("EXPIRED", 310)
    split_day = raw["date"][290]
    raw = raw.with_columns([
        pl.when(pl.col("date") >= split_day).then(pl.col(c) / 2).otherwise(pl.col(c)).alias(c)
        for c in ["open", "high", "low", "close"]
    ] + [pl.when(pl.col("date") >= split_day).then(pl.col("volume") * 2)
         .otherwise(pl.col("volume")).alias("volume")])
    adjusted = CorporateActionAdjustor.adjust_ohlcv(raw, pl.DataFrame({"date": [split_day], "factor": [2.]}))
    mixed = FeatureCalculator.calculate_features(adjusted)
    # Economically equivalent reference projection on one consistent adjusted basis.
    projected = adjusted.with_columns([pl.col(f"adj_{c}").alias(c)
                                      for c in ["open", "high", "low", "close", "volume"]])
    reference = FeatureCalculator.calculate_features(projected)
    when = raw["date"][260]
    detector = BreakoutDetector(CONFIG["BREAKOUT_V1"])
    actual_event = next(e for e in detector.detect("TEST_EXPIRED", mixed) if e.timestamp == when)
    expected_event = next(e for e in detector.detect("TEST_EXPIRED", reference) if e.timestamp == when)
    actual = OutcomeEngine({}).evaluate_event(actual_event, mixed)
    expected = OutcomeEngine({}).evaluate_event(expected_event, reference)
    assert expected["confirmation_date"] is None
    assert actual["confirmation_date"] is None, {
        "actual_confirmation": str(actual["confirmation_date"]), "raw_close": mixed["close"][260],
        "adjusted_close": mixed["adj_close"][260], "breakout_level": actual_event.breakout_level}


def test_discovery_outcomes_do_not_overlap_validation():
    dates = sessions(400)
    engine = ResearchEngine(OutcomeEngine({}))
    base = pl.DataFrame({"date": dates})
    discovery, validation, holdout = engine.split_data(base)
    detection = discovery["date"].max()
    index = dates.index(detection)
    prices = [99. if i < index + 4 else 101. for i in range(400)]
    df = base.with_columns(pl.lit("A").alias("instrument_id"), pl.Series("open", prices),
                           pl.Series("close", prices), pl.Series("high", [p + 1 for p in prices]),
                           pl.Series("low", [p - .5 for p in prices]))
    event = SetupEvent("A", "BREAKOUT_V1.0", detection, 100., {"atr_14": 4.})
    result = engine.run_backtest([event], df).row(0, named=True)
    assert result["exit_date"] < validation["date"].min(), {
        "detection": str(detection), "validation_start": str(validation["date"].min()),
        "outcome_exit": str(result["exit_date"]), "holdout_start": str(holdout["date"].min())}


def test_zip_input_supported(tmp_path):
    path = tmp_path / "synthetic.csv.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("synthetic.csv", source_frame(n=1).write_csv())
    importer = NSEImporter(str(tmp_path), str(tmp_path / "processed"))
    output = importer.process_bhavcopy(str(path))
    assert pl.read_parquet(output).height == 1


def test_html_input_rejected_without_processed_output(tmp_path):
    path = tmp_path / "not_a_report.csv"
    path.write_text("<html><body>Access denied</body></html>")
    importer = NSEImporter(str(tmp_path), str(tmp_path / "processed"))
    with pytest.raises((ValueError, pl.exceptions.PolarsError)):
        importer.process_bhavcopy(str(path))
    assert not list((tmp_path / "processed").glob("*.parquet"))


def test_importer_rejects_invalid_ohlc_before_publication(tmp_path):
    path = tmp_path / "invalid.csv"
    source_frame(n=1).with_columns(pl.lit(-1.).alias("OpnPric")).write_csv(path)
    importer = NSEImporter(str(tmp_path), str(tmp_path / "processed"))
    with pytest.raises(ValueError):
        importer.process_bhavcopy(str(path))
    assert not list((tmp_path / "processed").glob("*.parquet"))


def test_importer_preserves_market_date_provenance(tmp_path):
    path = tmp_path / "synthetic.csv"
    source_frame(n=1).write_csv(path)
    importer = NSEImporter(str(tmp_path), str(tmp_path / "processed"))
    output = importer.process_bhavcopy(str(path))
    data = pl.read_parquet(output)
    manifest = pl.read_csv(tmp_path / "manifest.csv")
    assert manifest["market_date"][0] == "2020-01-01", manifest.to_dicts()
    assert {"source_file", "source_date"} <= set(data.columns)


def test_dashboard_has_no_hardcoded_validated_overview(monkeypatch):
    from equity_engine.dashboard import app
    captured = []
    class Column:
        def metric(self, label, value):
            captured.append((label, value))
    class Display:
        def columns(self, count): return [Column() for _ in range(count)]
        def title(self, *args): pass
        def subheader(self, *args): pass
        def info(self, *args): pass
    monkeypatch.setattr(app, "st", Display())
    app.render_overview()
    assert ("Data Quality", "VALID") not in captured, captured


def test_alert_consumes_frozen_evidence(tmp_path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setenv("TEST_ENV", "1")
    with patch.object(EvidenceSnapshot, "load_snapshot") as load:
        alert = TelegramAlerter(str(tmp_path / "outbox.db"))
        try:
            assert alert.send_alert("review-only", "A", "BREAKOUT_V1.0", "Local test; never sent")
            assert load.called, "send_alert accepts caller text without loading frozen evidence."
        finally:
            alert.conn.close()


def test_actual_pilot_executes_partitions_and_snapshots(tmp_path, monkeypatch):
    (tmp_path / "data/raw").mkdir(parents=True)
    (tmp_path / "data/processed").mkdir()
    pl.concat([source_frame(s) for s in ["BREAKOUT", "VCB", "EXPIRED", "CENSORED", "INVALID"]]).write_csv(
        tmp_path / "data/raw/NSE_Pilot_Bhavcopy.csv")
    # An empty typed actions file; split semantics are tested separately above.
    pl.DataFrame(schema={"TradDt": pl.String, "TckrSymb": pl.String, "Ratio": pl.Float64}).write_csv(
        tmp_path / "data/raw/NSE_Pilot_CorpActions.csv")
    pl.DataFrame({"date": [d.isoformat() for d in sessions(340)], "close": [100.] * 340}).write_csv(
        tmp_path / "data/raw/NIFTY50.csv")
    monkeypatch.chdir(tmp_path)
    with patch.object(ResearchEngine, "split_data", autospec=True,
                      side_effect=ResearchEngine.split_data) as split, \
         patch.object(EvidenceSnapshot, "create_snapshot", autospec=True,
                      side_effect=EvidenceSnapshot.create_snapshot) as snapshot:
        runpy.run_path(str(ROOT / "scripts/run_pilot_pipeline.py"))["run_pilot"]()
        outcomes = pl.read_parquet(tmp_path / "data/processed/pilot_outcomes.parquet")
        summary = {"split_calls": split.call_count, "snapshot_calls": snapshot.call_count,
                   "states": dict(Counter(outcomes["final_state"].to_list())),
                   "setup_families": sorted(outcomes["setup"].unique().to_list())}
        (DEST / "pilot_execution.json").write_text(json.dumps(summary, indent=2))
        assert outcomes.filter(pl.col("final_state") == "COMPLETED").height > 0
        assert split.called and snapshot.called, summary
