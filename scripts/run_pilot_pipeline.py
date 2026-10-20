"""Execute the existing V1 methodology with auditable chronological evidence."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

import polars as pl
import yaml

from equity_engine.ingestion.nse_importer import NSEImporter
from equity_engine.ingestion.validator import DataValidator
from equity_engine.ingestion.quality import assess_quality
from equity_engine.corporate_actions.adjustor import CorporateActionAdjustor
from equity_engine.features.calculator import FeatureCalculator
from equity_engine.universe.builder import UniverseBuilder
from equity_engine.regime.classifier import RegimeClassifier
from equity_engine.setups.breakout import BreakoutDetector
from equity_engine.setups.vcb import VCBDetector
from equity_engine.outcomes.engine import OutcomeEngine
from equity_engine.backtest.engine import ResearchEngine
from equity_engine.backtest.controls import ControlEngine
from equity_engine.evidence.snapshot import EvidenceSnapshot

ROOT = Path(__file__).resolve().parents[1]
PARTITIONS = ("discovery", "validation", "holdout")
METHODOLOGY_VERSION = "V1-partitioned-pilot-1"
RESEARCH_DEFAULTS = {"discovery_pct": 0.6, "validation_pct": 0.2,
                     "timeout_days": 20, "watch_expiry_days": 5}
EVENT_SCHEMA = {
    "event_id": pl.String, "instrument_id": pl.String, "symbol": pl.String,
    "setup": pl.String, "detection_date": pl.Date, "breakout_level": pl.Float64,
    "partition": pl.String, "universe_eligible": pl.Boolean, "tier": pl.String,
    "exclusion_reason": pl.String, "regime": pl.String,
    "source_file": pl.String, "source_date": pl.String,
    "source_sha256": pl.String, "traded_value": pl.Float64,
}


def _hash_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, indent=2, default=str).encode("utf-8")


def _file_record(path, run_dir=None):
    path = Path(path).resolve()
    record = {"path": str(path), "sha256": _hash_bytes(path.read_bytes())}
    if run_dir is not None:
        record["relative_path"] = path.relative_to(run_dir).as_posix()
    return record


def _load_actions(path):
    if path is None:
        return pl.DataFrame(schema={"date": pl.Date, "symbol": pl.String, "factor": pl.Float64})
    frame = pl.read_csv(path)
    aliases = {"TradDt": "date", "TckrSymb": "symbol", "Ratio": "factor"}
    frame = frame.rename({old: new for old, new in aliases.items() if old in frame.columns})
    if not {"date", "factor"} <= set(frame.columns) or not {"symbol", "instrument_id"} & set(frame.columns):
        raise ValueError("Corporate actions require ex-date, factor and source symbol or instrument_id")
    type_column = "ActionType" if "ActionType" in frame.columns else "action_type"
    if type_column in frame.columns and frame.filter(
        pl.col(type_column).is_null() | ~pl.col(type_column).is_in(["SPLIT", "BONUS"])
    ).height:
        raise ValueError("Only explicit split/bonus action types are supported")
    identity = "instrument_id" if "instrument_id" in frame.columns else "symbol"
    if frame.filter(pl.col(identity).is_null() | (pl.col(identity).cast(pl.String).str.strip_chars() == "")).height:
        raise ValueError(f"Corporate action {identity} cannot be missing or blank")
    frame = frame.with_columns(pl.col("date").cast(pl.String).str.to_date("%Y-%m-%d"),
                               pl.col("factor").cast(pl.Float64))
    if frame.filter(pl.col("date").is_null() | pl.col("factor").is_null() |
                    ~pl.col("factor").is_finite() | (pl.col("factor") <= 0)).height:
        raise ValueError("Corporate action dates and positive finite factors are required")
    return frame


def _load_index(path):
    if path is None:
        return pl.DataFrame(schema={"date": pl.Date, "close": pl.Float64})
    frame = pl.read_csv(path).with_columns(pl.col("date").cast(pl.String).str.to_date("%Y-%m-%d"))
    if frame["date"].null_count() or frame["date"].n_unique() != frame.height:
        raise ValueError("Index data must have unique non-null dates")
    if frame.filter(pl.col("close").is_null() | ~pl.col("close").is_finite() | (pl.col("close") <= 0)).height:
        raise ValueError("Index closes must be finite and positive")
    return frame.sort("date")


def _load_calendar(path):
    if path is None:
        return None
    calendar = pl.read_csv(path).select(pl.col("date").str.to_date("%Y-%m-%d"))
    if calendar.is_empty() or calendar["date"].null_count() or calendar["date"].n_unique() != calendar.height:
        raise ValueError("Calendar must contain unique non-null session dates")
    return calendar.sort("date")


def _regime(day, index, features, eligible, configuration):
    history = index.filter(pl.col("date") <= day)
    if history.height < 200 or history["date"].max() != day:
        return "UNKNOWN", "missing_or_stale_index"
    current = features.filter((pl.col("date") == day) & pl.col("instrument_id").is_in(eligible))
    current = current.filter(pl.col("sma_50").is_not_null())
    breadth = None
    if current.height:
        value = current.select((pl.col("adj_close") > pl.col("sma_50")).mean()).item()
        breadth = pl.DataFrame({"date": [day], "pct_above_50_dma": [value]})
    value = RegimeClassifier(configuration).classify_regime(history, breadth_history=breadth)
    return value.value, "vix" + (",breadth" if breadth is None else "")


def _empty_statistics():
    return {"effective_n": 0, "distinct_time_blocks": 0, "mean_r": None,
            "baseline_type": "STATIC", "status": "INSUFFICIENT EVIDENCE",
            "dependence_limitation": "No completed eligible observations; no edge inference is available."}


def run_pilot(input_path=None, *, corporate_actions_path=None, index_path=None,
              config_dir=None, output_dir=None, raw_dir=None,
              source_provenance_path=None, seed=42, cohort=None, calendar_path=None):
    """Preserve source fields and execute each partition with bounded outcomes.

    input_path accepts one CSV/ZIP or a sequence of daily files. Earlier bars
    warm up causal features; only the selected partition supplies outcome bars.
    Universe eligibility is evaluated as of each candidate event's own date.
    Every invocation preserves a separate run directory and manifest.
    """
    legacy_defaults = input_path is None
    input_path = input_path or Path("data/raw/NSE_Pilot_Bhavcopy.csv")
    paths = [Path(input_path)] if isinstance(input_path, (str, Path)) else [Path(item) for item in input_path]
    if not paths:
        raise ValueError("At least one NSE input file is required")
    if source_provenance_path and len(paths) != 1:
        raise ValueError("Use adjacent acquisition receipts for multiple daily files")
    if legacy_defaults and corporate_actions_path is None:
        candidate = Path("data/raw/NSE_Pilot_CorpActions.csv")
        corporate_actions_path = candidate if candidate.exists() else None
    if legacy_defaults and index_path is None:
        candidate = Path("data/raw/NIFTY50.csv")
        index_path = candidate if candidate.exists() else None
    config_dir = Path(config_dir) if config_dir else ROOT / "config"
    configuration, config_files = {}, {}
    for name in ("setups", "universe", "costs", "regime"):
        path = config_dir / f"{name}.yaml"
        configuration[name] = yaml.safe_load(path.read_text(encoding="utf-8"))
        config_files[name] = _file_record(path)
    research_path = config_dir / "research.yaml"
    research = dict(RESEARCH_DEFAULTS)
    if research_path.exists():
        research.update(yaml.safe_load(research_path.read_text(encoding="utf-8")) or {})
        config_files["research"] = _file_record(research_path)
    for name in ("timeout_days", "watch_expiry_days"):
        if isinstance(research[name], bool) or not isinstance(research[name], int) or research[name] <= 0:
            raise ValueError(f"{name} must be a positive session count")
    configuration["research"] = research
    configuration["cohort"] = sorted(set(cohort)) if cohort is not None else None
    costs = configuration["costs"]["costs"]
    outcome_engine = OutcomeEngine({"timeout_days": research["timeout_days"],
                                    "watch_expiry_days": research["watch_expiry_days"],
                                    "transaction_costs": costs})
    research_engine = ResearchEngine(outcome_engine)
    importer = NSEImporter(str(raw_dir or "data/raw/official"),
                           str(Path(output_dir or "data/processed/pilot_runs") / "normalized"))
    frames, inputs, seen = [], [], set()
    for path in paths:
        acquisition, acquisition_record = {}, None
        provenance_path = Path(source_provenance_path) if source_provenance_path else path.with_name(path.name + ".provenance.json")
        if source_provenance_path and not provenance_path.is_file():
            raise FileNotFoundError(f"Requested acquisition receipt not found: {provenance_path}")
        input_bytes = path.read_bytes()
        input_digest = _hash_bytes(input_bytes)
        if provenance_path.exists():
            metadata = json.loads(provenance_path.read_text(encoding="utf-8"))
            if metadata.get("sha256") != input_digest or metadata.get("bytes") != len(input_bytes):
                raise ValueError("Acquisition receipt does not match source bytes")
            acquisition = {"source_url": metadata.get("final_url") or metadata.get("requested_url"),
                           "downloaded_at": metadata.get("downloaded_at_utc")}
            acquisition_record = _file_record(provenance_path)
        if input_digest in seen:
            continue
        seen.add(input_digest)
        normalized = importer.process_bhavcopy(str(path), **acquisition)
        frames.append(pl.read_parquet(normalized))
        receipt = importer.processed_dir / "receipts" / f"{normalized.stem}.json"
        receipt_metadata = json.loads(receipt.read_text(encoding="utf-8"))
        if receipt_metadata["input_sha256"] != input_digest:
            raise ValueError("Source bytes changed during ingestion")
        inputs.append({"kind": "ohlcv", "path": str(path.resolve()), "sha256": input_digest,
                       "archived_raw": _file_record(receipt_metadata["raw_path"]), "acquisition": acquisition,
                       "acquisition_receipt": acquisition_record, "normalized": _file_record(normalized),
                       "ingestion_receipt": _file_record(receipt)})
    raw = pl.concat(frames, how="diagonal_relaxed").sort(["instrument_id", "date"])
    DataValidator.validate_ohlcv(raw)
    if cohort is not None:
        raw = raw.filter(pl.col("instrument_id").is_in(cohort) | pl.col("symbol").is_in(cohort))
    if raw.is_empty():
        raise ValueError("The requested cohort has no source bars")
    if not {"instrument_id", "traded_value", "source_sha256"} <= set(raw.columns):
        raise ValueError("Production data must retain source identity, turnover and provenance")
    actions = _load_actions(corporate_actions_path)
    index = _load_index(index_path)
    calendar = _load_calendar(calendar_path)
    for kind, path in (("corporate_actions", corporate_actions_path), ("index", index_path),
                       ("calendar", calendar_path)):
        if path is not None:
            inputs.append({"kind": kind, **_file_record(path)})
    if "instrument_id" not in actions.columns and actions.height:
        ambiguity = raw.group_by("symbol").agg(pl.col("instrument_id").n_unique().alias("identities"))
        if ambiguity.filter((pl.col("identities") > 1) & pl.col("symbol").is_in(actions["symbol"].to_list())).height:
            raise ValueError("Reused symbols require explicit instrument_id in corporate actions")
    feature_frames = []
    for instrument in raw["instrument_id"].unique().sort().to_list():
        history = raw.filter(pl.col("instrument_id") == instrument)
        selected = actions.filter(pl.col("instrument_id") == instrument) if "instrument_id" in actions.columns else actions.filter(pl.col("symbol").is_in(history["symbol"].unique().to_list()))
        selected = selected.filter(pl.col("date") <= raw["date"].max())
        adjusted = CorporateActionAdjustor.adjust_ohlcv(history, selected.select("date", "factor"))
        feature_frames.append(FeatureCalculator.calculate_features(adjusted))
    features = pl.concat(feature_frames, how="diagonal_relaxed").sort(["instrument_id", "date"])
    parts = dict(zip(PARTITIONS, research_engine.split_data(features, research["discovery_pct"], research["validation_pct"])))
    boundaries = {name: {"start": str(frame["date"].min()) if frame.height else None,
                         "end": str(frame["date"].max()) if frame.height else None,
                         "sessions": frame["date"].n_unique()} for name, frame in parts.items()}
    detectors = [BreakoutDetector(configuration["setups"]["setups"]["BREAKOUT_V1"]),
                 VCBDetector(configuration["setups"]["setups"]["VCB_V1"])]
    detected = []
    for instrument in features["instrument_id"].unique().sort().to_list():
        history = features.filter(pl.col("instrument_id") == instrument)
        for detector in detectors:
            detected.extend(detector.detect(instrument, history))
    detected.sort(key=lambda event: (event.timestamp, event.instrument_id, event.setup_version))
    builder = UniverseBuilder(configuration["universe"])
    daily_membership, regime_values, universe_frames, regime_rows = {}, {}, [], []
    for day in sorted({event.timestamp for event in detected}):
        eligible = builder.build_daily_universe(day, raw)
        daily_membership[day] = {row["instrument_id"]: row["tier"] for row in eligible.iter_rows(named=True)}
        universe_frames.append(eligible.with_columns(pl.lit(day, dtype=pl.Date).alias("date")))
        regime, missing = _regime(day, index, features, eligible["instrument_id"].to_list(), configuration["regime"])
        regime_values[day] = regime
        regime_rows.append({"date": day, "regime": regime, "missing_inputs": missing})
    universe = pl.concat(universe_frames, how="diagonal_relaxed") if universe_frames else builder.build_daily_universe(raw["date"].min(), raw.head(0)).with_columns(pl.lit(None, dtype=pl.Date).alias("date"))
    regime_frame = pl.DataFrame(regime_rows, schema={"date": pl.Date, "regime": pl.String, "missing_inputs": pl.String})
    event_rows, accepted = [], {name: [] for name in PARTITIONS}
    for event in detected:
        partition = next((name for name, frame in parts.items() if frame.height and frame["date"].min() <= event.timestamp <= frame["date"].max()), "purged")
        tier = daily_membership[event.timestamp].get(event.instrument_id)
        source = raw.filter((pl.col("instrument_id") == event.instrument_id) & (pl.col("date") == event.timestamp)).row(0, named=True)
        event_rows.append({"event_id": event.event_id, "instrument_id": event.instrument_id,
                           "symbol": source["symbol"], "setup": event.setup_version,
                           "detection_date": event.timestamp, "breakout_level": event.breakout_level,
                           "partition": partition, "universe_eligible": tier is not None,
                           "tier": tier, "regime": regime_values[event.timestamp],
                           "exclusion_reason": "PURGE_GAP" if partition == "purged" else ("UNIVERSE_INELIGIBLE" if tier is None else None),
                           **{column: source[column] for column in ("source_file", "source_date", "source_sha256", "traded_value")}})
        if partition != "purged" and tier is not None:
            accepted[partition].append(event)
    events = pl.DataFrame(event_rows, schema=EVENT_SCHEMA, strict=False)
    outcome_frames = []
    for name, frame in parts.items():
        outcome_frames.append(research_engine.run_backtest(accepted[name], frame, partition=name,
                              partition_start=frame["date"].min(), partition_end=frame["date"].max()))
    outcomes = pl.concat(outcome_frames)
    context = events.select("event_id", "symbol", "tier", "regime", "source_file", "source_date", "source_sha256", "traded_value")
    outcomes = outcomes.join(context, on="event_id", how="left").sort(["partition", "detection_date", "instrument_id", "setup"])

    configuration_hash = _hash_bytes(_json_bytes(configuration))
    input_hash = _hash_bytes(_json_bytes(sorted((item["kind"], item["sha256"]) for item in inputs)))
    source_paths = [Path(__file__)] + sorted((ROOT / "src/equity_engine").rglob("*.py"))
    code_hash = _hash_bytes(_json_bytes({str(path.relative_to(ROOT)): _hash_bytes(path.read_bytes()) for path in source_paths}))
    fingerprint = _hash_bytes(_json_bytes({"input_hash": input_hash, "configuration_hash": configuration_hash,
                                          "code_hash": code_hash, "seed": seed, "methodology": METHODOLOGY_VERSION}))
    trial_id = f"pilot-{fingerprint[:16]}-{uuid.uuid4().hex[:8]}"
    run_dir = Path(output_dir or "data/processed/pilot_runs").resolve() / trial_id
    run_dir.mkdir(parents=True, exist_ok=False)
    quality = assess_quality(raw, features, inputs, cohort=cohort, calendar=calendar,
                             actions=actions, index=index,
                             warmup_sessions=max(settings["parameters"]["lookback_days"]
                                 for settings in configuration["setups"]["setups"].values()))
    quality.update(trial_id=trial_id, input_hash=input_hash, configuration_hash=configuration_hash,
                   code_hash=code_hash, run_fingerprint=fingerprint)
    quality_path = run_dir / "quality.json"
    quality_path.write_bytes(_json_bytes(quality))
    quality_record = _file_record(quality_path, run_dir)
    outcomes = outcomes.with_columns(pl.lit(
        None if quality["evidence_allowed"] else "DATA_QUALITY_FAILED", dtype=pl.String
    ).alias("evidence_withheld_reason"))
    if not quality["evidence_allowed"]:
        outcomes = outcomes.with_columns(pl.lit(False).alias("evidence_eligible"))
    outputs = {"quality": quality_record}
    for name, frame in (("features", features), ("universe", universe), ("events", events),
                         ("outcomes", outcomes), ("regime", regime_frame)):
        path = run_dir / f"{name}.parquet"
        frame.write_parquet(path)
        outputs[name] = _file_record(path, run_dir)
    snapshot_manager = EvidenceSnapshot(str(run_dir))
    snapshots, statistics, partition_results = [], [], {}
    versions = [f"BREAKOUT_V{configuration['setups']['setups']['BREAKOUT_V1']['version']}",
                f"VCB_V{configuration['setups']['setups']['VCB_V1']['version']}"]
    for name, frame in parts.items():
        partition_outcomes = outcomes.filter(pl.col("partition") == name)
        partition_results[name] = {"events": partition_outcomes.height,
                                   "censored": partition_outcomes.filter(pl.col("censored")).height,
                                   "eligible": partition_outcomes.filter(pl.col("evidence_eligible")).height,
                                   "status": "NO_SESSIONS" if frame.is_empty() else "EXECUTED"}
        if frame.is_empty() or not quality["evidence_allowed"]:
            continue
        for version in versions:
            family = partition_outcomes.filter((pl.col("setup") == version) & pl.col("evidence_eligible"))
            metrics = ControlEngine.calculate_metrics(family, seed=seed) if family.height else _empty_statistics()
            statistics.append({"partition": name, "setup_version": version, "statistics": metrics})
            snapshot_id = snapshot_manager.create_snapshot(
                setup_version=version,
                universe_version=f"universe-{configuration['universe'].get('version', 'unversioned')}",
                methodology_version=METHODOLOGY_VERSION, data_cutoff=frame["date"].max(),
                statistics=metrics, outcomes_df=family,
                trial_id=trial_id, partition=name, configuration=configuration, cost_model=costs,
                date_boundaries=boundaries, input_hash=input_hash, configuration_hash=configuration_hash,
                code_hash=code_hash, random_seed=seed, price_basis_cutoff=str(raw["date"].max()),
                quality_sha256=quality_record["sha256"],
            )
            snapshots.append({"partition": name, "setup_version": version, "snapshot_id": snapshot_id,
                              "metadata": _file_record(snapshot_manager.snapshots_dir / f"{snapshot_id}_meta.json", run_dir),
                              "outcomes": _file_record(snapshot_manager.snapshots_dir / f"{snapshot_id}_outcomes.parquet", run_dir)})
    statistics_path = run_dir / "statistics.json"
    statistics_path.write_bytes(_json_bytes(statistics))
    outputs["statistics"] = _file_record(statistics_path, run_dir)
    warnings = []
    if corporate_actions_path is None:
        warnings.append("No corporate-action source supplied; this is not proof of action-free history.")
    if index_path is None:
        warnings.append("No index source supplied; event regime is UNKNOWN.")
    if any(not item.get("acquisition") for item in inputs if item["kind"] == "ohlcv"):
        warnings.append("Some source files have no recorded acquisition provenance.")
    manifest = {"schema_version": 2, "artifact_path_contract": "run-relative-v1",
                "trial_id": trial_id, "run_dir": str(run_dir), "run_fingerprint": fingerprint,
                "manifest_path": str(run_dir / "manifest.json"),
                "created_at": datetime.now(timezone.utc).isoformat(), "execution_status": "COMPLETED",
                "status": "DATA QUALITY FAILED" if not quality["evidence_allowed"] else (
                    "INSUFFICIENT EVIDENCE" if not outcomes.filter(pl.col("evidence_eligible")).height else "EXPERIMENTAL"),
                "quality_status": quality["status"],
                "methodology_version": METHODOLOGY_VERSION, "setup_versions": versions,
                "universe_version": f"universe-{configuration['universe'].get('version', 'unversioned')}",
                "random_seed": seed, "configuration": configuration, "cost_model": costs,
                "cost_rate_per_side": outcome_engine.cost_rate, "configuration_hash": configuration_hash,
                "code_hash": code_hash, "input_hash": input_hash, "inputs": inputs,
                "configuration_files": config_files, "date_boundaries": boundaries,
                "universe_evaluation": "as_of_each_candidate_detection_date_using_reported_turnover",
                "price_basis": {"method": "backward_split_bonus_adjustment", "cutoff": str(raw["date"].max()),
                                "raw_ohlcv_retained": True},
                "regime_breadth_population": "eligible_instruments_in_supplied_pilot_cohort",
                "outcome_boundary_policy": "censor_incomplete_windows_at_each_partition_end",
                "counts": {"candidate_events": events.height, "evaluated_events": outcomes.height,
                           "eligible_outcomes": outcomes.filter(pl.col("evidence_eligible")).height},
                "partition_results": partition_results, "outputs": outputs,
                "snapshots": snapshots, "warnings": warnings, "paper_research_approved": False}
    manifest_bytes = _json_bytes(manifest)
    (run_dir / "manifest.json").write_bytes(manifest_bytes)
    (run_dir / "manifest.sha256").write_text(_hash_bytes(manifest_bytes) + "\n", encoding="utf-8")
    print(f"Completed {trial_id}: {outcomes.height} outcomes; artifacts in {run_dir}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="*", type=Path)
    parser.add_argument("--corporate-actions", type=Path)
    parser.add_argument("--index", type=Path)
    parser.add_argument("--calendar", type=Path, help="CSV date column: explicit expected sessions covering this run")
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--provenance", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cohort", nargs="+")
    args = parser.parse_args()
    run_pilot(args.input or None, corporate_actions_path=args.corporate_actions,
              index_path=args.index, config_dir=args.config_dir, output_dir=args.output_dir,
              raw_dir=args.raw_dir, source_provenance_path=args.provenance,
              seed=args.seed, cohort=args.cohort, calendar_path=args.calendar)


if __name__ == "__main__":
    main()

