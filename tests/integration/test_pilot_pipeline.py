"""Acceptance checks of the production entry point with synthetic NSE-shaped data.

These fixtures prove pipeline wiring. Official-file fidelity is covered by the
separate official NSE importer tests, rather than inferred from these fixtures.
"""

from datetime import date, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
from unittest.mock import patch

import polars as pl
import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
IDENTIFIERS = {
    "BREAKOUT": "INE001A01011",
    "VCB": "INE002A01011",
    "ILLIQUID": "INE003A01011",
    "BOUNDARY": "INE004A01011",
    "SPARSE": "INE005A01011",
    "STATIC": "INE006A01011",
}


def _sessions(count):
    result, current = [], date(2018, 1, 1)
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return result


def _source_rows(symbol, dates, *, quiet=False):
    rows = []
    pulses = [350, 800, 1100] if not quiet else []
    for index, session in enumerate(dates):
        if symbol == "SPARSE" and 721 <= index <= 740:
            continue
        opening, high, low, close, volume = 100.0, 101.0, 99.0, 100.0, 1000
        if symbol in {"BREAKOUT", "ILLIQUID"}:
            for pulse in pulses:
                if index == pulse:
                    volume = 2000
                elif index == pulse + 1:
                    opening, high, low, close = 101.0, 103.0, 100.0, 102.0
                elif pulse + 2 <= index <= pulse + 27:
                    opening, high, low, close = 103.0, 104.0, 102.0, 103.0
        elif symbol == "VCB":
            high, low = 110.0, 90.0
            for pulse in pulses:
                if pulse - 60 <= index < pulse:
                    high, low = 100.5, 99.5
                elif index == pulse:
                    opening, high, low, close, volume = 100.0, 101.0, 100.0, 100.75, 2000
                elif pulse < index <= pulse + 27:
                    opening, high, low, close = 101.0, 102.0, 100.75, 101.0
        elif symbol == "BOUNDARY" and not quiet:
            if index == 720:
                volume = 2000
            elif index == 724:
                opening, high, low, close = 101.0, 103.0, 100.0, 102.0
            elif 725 <= index <= 752:
                opening, high, low, close = 103.0, 104.0, 102.0, 103.0
        elif symbol == "SPARSE" and not quiet:
            if index == 719:
                volume = 2000
            elif index == 720:
                opening, high, low, close = 101.0, 103.0, 100.0, 102.0
            elif 741 <= index <= 770:
                opening, high, low, close = 103.0, 104.0, 102.0, 103.0
        if symbol == "ILLIQUID":
            # Deliberately contradict close * volume: eligibility must use the
            # supplied turnover, not an estimated turnover substituted upstream.
            volume *= 10000
        rows.append({
            "TradDt": session.isoformat(), "ISIN": IDENTIFIERS[symbol],
            "TckrSymb": symbol, "SctySrs": "EQ", "OpnPric": opening,
            "HghPric": high, "LwPric": low, "ClsPric": close,
            "TtlTradgVol": volume,
            "TtlTrfVal": 10000.0 if symbol == "ILLIQUID" else 1_000_000_000.0,
        })
    return rows


def _write_inputs(folder, *, quiet=False):
    folder.mkdir(parents=True)
    dates = _sessions(400 if quiet else 1200)
    symbols = ["STATIC"] if quiet else list(IDENTIFIERS)[:-1]
    source = folder / "synthetic_nse.csv"
    pl.DataFrame([row for symbol in symbols
                  for row in _source_rows(symbol, dates, quiet=quiet)]).write_csv(source)
    actions = folder / "actions.csv"
    pl.DataFrame(schema={"TradDt": pl.String, "TckrSymb": pl.String,
                         "Ratio": pl.Float64}).write_csv(actions)
    index = folder / "nifty.csv"
    pl.DataFrame({"date": dates, "close": [10000.0 + i for i in range(len(dates))]}).write_csv(index)
    configs = folder / "config"
    shutil.copytree(ROOT / "config", configs)
    return {"input_path": source, "corporate_actions_path": actions,
            "index_path": index, "config_dir": configs,
            "raw_dir": folder / "raw_archive", "seed": 42}, dates


@pytest.fixture(scope="module")
def production_module():
    spec = importlib.util.spec_from_file_location(
        "pilot_pipeline_acceptance", ROOT / "scripts" / "run_pilot_pipeline.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def pilot(tmp_path_factory, production_module):
    workspace = tmp_path_factory.mktemp("production_pilot")
    kwargs, dates = _write_inputs(workspace / "inputs")
    calls = {"split": [], "backtest": [], "snapshot": []}
    split = production_module.ResearchEngine.split_data
    backtest = production_module.ResearchEngine.run_backtest
    snapshot = production_module.EvidenceSnapshot.create_snapshot

    def split_spy(engine, frame, *args, **options):
        result = split(engine, frame, *args, **options)
        calls["split"].append((frame, result))
        return result

    def backtest_spy(engine, events, history, *args, **options):
        result = backtest(engine, events, history, *args, **options)
        calls["backtest"].append((list(events), history, options, result))
        return result

    def snapshot_spy(manager, *args, **options):
        snapshot_id = snapshot(manager, *args, **options)
        calls["snapshot"].append((dict(options), snapshot_id))
        return snapshot_id

    with patch.object(production_module.ResearchEngine, "split_data", split_spy), \
            patch.object(production_module.ResearchEngine, "run_backtest", backtest_spy), \
            patch.object(production_module.EvidenceSnapshot, "create_snapshot", snapshot_spy):
        manifest = production_module.run_pilot(output_dir=workspace / "runs", **kwargs)
    return {"manifest": manifest, "calls": calls, "kwargs": kwargs,
            "dates": dates, "workspace": workspace}


def _output(manifest, name):
    return pl.read_parquet(manifest["outputs"][name]["path"])


def test_source_identifiers_turnover_and_configured_universe_reach_production(pilot):
    manifest = pilot["manifest"]
    features = _output(manifest, "features")
    universe = _output(manifest, "universe")
    events = _output(manifest, "events")
    outcomes = _output(manifest, "outcomes")
    for symbol, identifier in list(IDENTIFIERS.items())[:-1]:
        source_rows = features.filter(pl.col("symbol") == symbol)
        assert source_rows.height > 0
        assert source_rows["instrument_id"].unique().to_list() == [identifier]
        assert source_rows["traded_value"].unique().to_list() == [
            10000.0 if symbol == "ILLIQUID" else 1_000_000_000.0]
    assert {"date", "instrument_id", "symbol", "tier"} <= set(universe.columns)
    assert set(universe["instrument_id"]) <= set(IDENTIFIERS.values())
    assert universe.filter(pl.col("symbol") == "BREAKOUT").height > 0
    assert universe.filter(pl.col("symbol") == "ILLIQUID").is_empty()
    illiquid_candidates = events.filter(pl.col("instrument_id") == IDENTIFIERS["ILLIQUID"])
    assert illiquid_candidates.height >= 3, "Fixture must actually generate excluded candidates"
    assert not illiquid_candidates["universe_eligible"].any()
    assert outcomes.filter(pl.col("instrument_id") == IDENTIFIERS["ILLIQUID"]).is_empty()
    for filename in ["setups.yaml", "universe.yaml", "costs.yaml", "regime.yaml"]:
        expected = yaml.safe_load((ROOT / "config" / filename).read_text())
        resolved = manifest["configuration"][filename.removesuffix(".yaml")]
        assert resolved == expected
    assert manifest["cost_model"] == yaml.safe_load((ROOT / "config" / "costs.yaml").read_text())["costs"]
    costs = manifest["cost_model"]
    fee_per_side = sum(costs[key] for key in [
        "slippage_pct", "brokerage_pct", "stt_pct", "exchange_charges_pct",
        "sebi_charges_pct", "stamp_duty_pct"])
    fee_per_side += costs["gst_pct"] * sum(costs[key] for key in [
        "brokerage_pct", "exchange_charges_pct", "sebi_charges_pct"])
    completed = outcomes.filter(pl.col("evidence_eligible"))
    assert completed.height > 0
    for row in completed.iter_rows(named=True):
        expected_net = ((row["exit_price"] - row["entry_price"]) -
                        (row["entry_price"] + row["exit_price"]) * fee_per_side)
        expected_net /= row["entry_price"] - row["stop_price"]
        assert row["net_realized_r"] == pytest.approx(expected_net)


def test_actual_backtests_execute_three_separate_chronological_partitions(pilot):
    calls = pilot["calls"]
    assert len(calls["split"]) == 1
    assert len(calls["backtest"]) == 3
    expected_partitions = ["DISCOVERY", "VALIDATION", "HOLDOUT"]
    prior_end = None
    for expected, partition, call in zip(
            expected_partitions, calls["split"][0][1], calls["backtest"]):
        events, history, options, outcomes = call
        assert options["partition"].upper() == expected
        assert history.height == partition.height
        assert history.sort(["instrument_id", "date"]).equals(
            partition.sort(["instrument_id", "date"]))
        start, end = history["date"].min(), history["date"].max()
        assert options["partition_start"] == start
        assert options["partition_end"] == end
        if prior_end is not None:
            assert prior_end < start
        prior_end = end
        assert events, f"Fixture must exercise events in {expected}"
        assert all(start <= event.timestamp <= end for event in events)
        assert outcomes["partition"].unique().to_list() == [expected.lower()]
        assert outcomes["is_oos"].unique().to_list() == [expected != "DISCOVERY"]
        assert outcomes.filter(pl.col("exit_date") > end).is_empty()
        completed = outcomes.filter(pl.col("evidence_eligible"))
        assert completed.height >= 2, f"No completed-event vacuity allowed in {expected}"
        assert {"BREAKOUT", "VCB"} == {
            "BREAKOUT" if value.startswith("BREAKOUT_") else "VCB"
            for value in completed["setup"].unique()}


def test_boundary_and_sparse_outcomes_are_censored_before_frozen_evidence(pilot):
    outcomes = _output(pilot["manifest"], "outcomes")
    boundary_ids = [IDENTIFIERS["BOUNDARY"], IDENTIFIERS["SPARSE"]]
    boundary = outcomes.filter(pl.col("instrument_id").is_in(boundary_ids))
    assert set(boundary["instrument_id"]) == set(boundary_ids)
    assert boundary["partition"].unique().to_list() == ["discovery"]
    assert boundary["censored"].all()
    assert not boundary["evidence_eligible"].any()
    assert boundary["net_realized_r"].null_count() == boundary.height
    assert boundary["exit_date"].null_count() == boundary.height
    assert set(boundary["final_state"]) <= {"WATCH", "CONFIRMED"}
    evidence_rows = 0
    for options, _ in pilot["calls"]["snapshot"]:
        frozen = options["outcomes_df"]
        evidence_rows += frozen.height
        assert frozen.filter(pl.col("instrument_id").is_in(boundary_ids)).is_empty()
        assert frozen.filter(pl.col("censored")).is_empty()
        assert frozen["evidence_eligible"].all()
        assert frozen.filter(pl.col("exit_date") > options["data_cutoff"]).is_empty()
        if frozen.height:
            assert frozen["partition"].n_unique() == 1
            assert frozen["setup"].n_unique() == 1
    assert evidence_rows >= 6


def test_run_manifest_and_snapshots_link_real_inputs_configuration_and_hashes(pilot, production_module):
    manifest = pilot["manifest"]
    assert manifest["trial_id"]
    assert len(manifest["input_hash"]) == 64
    assert manifest["random_seed"] == 42
    assert manifest["date_boundaries"]
    run_dir = Path(manifest["run_dir"])
    assert run_dir.is_dir()
    persisted = json.loads(Path(manifest["manifest_path"]).read_text())
    assert persisted == manifest
    for artifact in manifest["outputs"].values():
        path = Path(artifact["path"])
        assert path.is_file()
        assert path.resolve().is_relative_to(run_dir.resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
    assert manifest["snapshots"]
    snapshots = production_module.EvidenceSnapshot(str(run_dir))
    for entry in manifest["snapshots"]:
        metadata, frozen = snapshots.load_snapshot(entry["snapshot_id"])
        assert metadata["trial_id"] == manifest["trial_id"]
        assert metadata["configuration"] == manifest["configuration"]
        assert metadata["cost_model"] == manifest["cost_model"]
        assert metadata["input_hash"] == manifest["input_hash"]
        assert metadata["random_seed"] == 42
        assert metadata["methodology_version"]
        assert metadata["universe_version"]
        assert metadata["partition"].upper() == entry["partition"].upper()
        assert metadata["setup_version"] == entry["setup_version"]
        assert metadata["statistics"]["status"] != "VALIDATED", "A few synthetic observations cannot validate"
        assert metadata["statistics"].get("dependence_limitation")
        if frozen.height:
            assert frozen["partition"].n_unique() == 1
            assert frozen["setup"].n_unique() == 1
            assert frozen.filter(pl.col("exit_date") > date.fromisoformat(metadata["data_cutoff"])).is_empty()


def test_replaying_production_preserves_event_identity_outcomes_and_statistics(pilot, production_module):
    original = pilot["manifest"]
    replay = production_module.run_pilot(
        output_dir=pilot["workspace"] / "replayed_runs", **pilot["kwargs"])
    assert replay["input_hash"] == original["input_hash"]
    for name, ordering in [("events", ["event_id"]), ("outcomes", ["event_id", "partition"])]:
        first, second = _output(original, name), _output(replay, name)
        columns = [column for column in first.columns if column not in {"trial_id", "created_at"}]
        assert first.select(columns).sort(ordering).equals(second.select(columns).sort(ordering))
    def statistics(manifest):
        manager = production_module.EvidenceSnapshot(manifest["run_dir"])
        return {(entry["partition"], entry["setup_version"]):
                manager.load_snapshot(entry["snapshot_id"])[0]["statistics"]
                for entry in manifest["snapshots"]}
    assert statistics(original) == statistics(replay)


def test_changed_future_prices_and_turnover_do_not_change_earlier_decisions(pilot, production_module):
    original = pilot["manifest"]
    future_start, decision_cutoff = pilot["dates"][900], pilot["dates"][800]
    changed_path = pilot["workspace"] / "future_changed.csv"
    source = pl.read_csv(pilot["kwargs"]["input_path"])
    source = source.with_columns(
        *[pl.when(pl.col("TradDt") >= future_start.isoformat())
          .then(pl.col(column) * 2).otherwise(pl.col(column)).alias(column)
          for column in ["OpnPric", "HghPric", "LwPric", "ClsPric"]],
        pl.when(pl.col("TradDt") >= future_start.isoformat())
        .then(10000.0).otherwise(pl.col("TtlTrfVal")).alias("TtlTrfVal"),
    )
    source.write_csv(changed_path)
    options = {**pilot["kwargs"], "input_path": changed_path}
    changed = production_module.run_pilot(
        output_dir=pilot["workspace"] / "future_changed_runs", **options)
    assert changed["input_hash"] != original["input_hash"]
    for name, date_column, ordering in [
            ("events", "detection_date", ["event_id"]),
            ("universe", "date", ["date", "instrument_id"])]:
        first = _output(original, name).filter(pl.col(date_column) <= decision_cutoff)
        second = _output(changed, name).filter(pl.col(date_column) <= decision_cutoff)
        columns = [column for column in first.columns if column not in {
            "trial_id", "created_at", "source_file", "source_sha256"}]
        assert first.height > 0
        assert first.select(columns).sort(ordering).equals(second.select(columns).sort(ordering))


def test_zero_event_production_run_publishes_typed_outputs_and_insufficient_evidence(tmp_path, production_module):
    kwargs, _ = _write_inputs(tmp_path / "quiet_inputs", quiet=True)
    manifest = production_module.run_pilot(output_dir=tmp_path / "quiet_runs", **kwargs)
    events, outcomes = _output(manifest, "events"), _output(manifest, "outcomes")
    assert events.is_empty() and outcomes.is_empty()
    assert events.schema["event_id"] == pl.String
    assert outcomes.schema["event_id"] == pl.String
    assert outcomes.schema["detection_date"] == pl.Date
    assert outcomes.schema["net_realized_r"] == pl.Float64
    assert outcomes.schema["censored"] == pl.Boolean
    assert manifest["status"] == "INSUFFICIENT EVIDENCE"
    assert manifest["snapshots"]
    manager = production_module.EvidenceSnapshot(manifest["run_dir"])
    for entry in manifest["snapshots"]:
        metadata, frozen = manager.load_snapshot(entry["snapshot_id"])
        assert frozen.is_empty()
        assert metadata["statistics"]["status"] == "INSUFFICIENT EVIDENCE"
        assert metadata["statistics"]["effective_n"] == 0


@pytest.mark.parametrize("changes", [
    {"instrument_id": None},
    {"instrument_id": " "},
    {"ActionType": None},
    {"ActionType": "DIVIDEND"},
    {"Ratio": -2.0},
    {"TradDt": None},
])
def test_malformed_action_rows_cannot_silently_disappear(tmp_path, production_module, changes):
    row = {"TradDt": "2020-01-01", "TckrSymb": "BREAKOUT",
           "instrument_id": IDENTIFIERS["BREAKOUT"], "Ratio": 2.0, "ActionType": "SPLIT"}
    row.update(changes)
    path = tmp_path / "invalid_actions.csv"
    pl.DataFrame([row]).write_csv(path)
    with pytest.raises(ValueError):
        production_module._load_actions(path)


def test_explicit_missing_acquisition_receipt_rejects_the_run(tmp_path, production_module):
    kwargs, _ = _write_inputs(tmp_path / "input", quiet=True)
    with pytest.raises(FileNotFoundError, match="acquisition receipt"):
        production_module.run_pilot(output_dir=tmp_path / "runs",
            source_provenance_path=tmp_path / "missing-receipt.json", **kwargs)
    assert not list((tmp_path / "runs").rglob("manifest.json"))


def test_production_keeps_terminal_losses_and_excludes_unfinished_or_invalid_evidence(tmp_path, production_module):
    kwargs, dates = _write_inputs(tmp_path / "inputs")
    source = pl.read_csv(kwargs["input_path"])
    template = source.filter(pl.col("TckrSymb") == "BREAKOUT")
    frames = [source]
    identifiers = {}
    for number, symbol in enumerate(["FAILED", "EXPIRED", "INVALID", "CENSORED"], 7):
        identifier = f"INE{number:03d}A01011"
        identifiers[symbol] = identifier
        frame = template.with_columns(pl.lit(symbol).alias("TckrSymb"), pl.lit(identifier).alias("ISIN"))
        if symbol in {"FAILED", "INVALID"}:
            changed_dates = [day.isoformat() for pulse in [350, 800, 1100] for day in dates[pulse + 2:pulse + 28]]
            values = [101.0, 102.0, 95.0, 96.0] if symbol == "FAILED" else [90.0, 91.0, 88.0, 89.0]
            frame = frame.with_columns([
                pl.when(pl.col("TradDt").is_in(changed_dates)).then(value).otherwise(pl.col(column)).alias(column)
                for column, value in zip(["OpnPric", "HghPric", "LwPric", "ClsPric"], values)])
        else:
            frame = frame.with_columns([pl.lit(value).alias(column) for column, value in
                [("OpnPric", 100.0), ("HghPric", 101.0), ("LwPric", 99.0), ("ClsPric", 100.0)]])
            if symbol == "CENSORED":
                frame = frame.with_columns(pl.when(pl.col("TradDt") == dates[-1].isoformat())
                    .then(2000).otherwise(1000).alias("TtlTradgVol"))
        frames.append(frame)
    pl.concat(frames, how="vertical_relaxed").write_csv(kwargs["input_path"])
    manifest = production_module.run_pilot(output_dir=tmp_path / "runs", **kwargs)
    outcomes = _output(manifest, "outcomes")
    for symbol, state in [("FAILED", "FAILED"), ("EXPIRED", "EXPIRED"),
                          ("INVALID", "INVALIDATED"), ("CENSORED", "WATCH")]:
        records = outcomes.filter(pl.col("instrument_id") == identifiers[symbol])
        assert records.height > 0
        assert records["final_state"].unique().to_list() == [state]
    losses = outcomes.filter(pl.col("instrument_id") == identifiers["FAILED"])
    assert losses["evidence_eligible"].all() and (losses["net_realized_r"] < 0).all()
    manager = production_module.EvidenceSnapshot(manifest["run_dir"])
    frozen = pl.concat([manager.load_snapshot(entry["snapshot_id"])[1] for entry in manifest["snapshots"]])
    assert frozen.filter(pl.col("instrument_id") == identifiers["FAILED"]).height == losses.height
    assert frozen.filter(pl.col("instrument_id").is_in([identifiers[key]
        for key in ["EXPIRED", "INVALID", "CENSORED"]])).is_empty()
