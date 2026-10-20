# Production V1 pilot runner

The runner composes the existing importer, corporate-action adjustor, features,
universe, regime, setup detectors, outcome/research engines and frozen evidence.
Existing setup thresholds and YAML files remain unchanged.

## Usage

```powershell
.venv\Scripts\python.exe scripts/run_pilot_pipeline.py tests/fixtures/nse/BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv.zip --cohort RELIANCE TCS HDFCBANK INFY ICICIBANK
```

The retained file contains one session. This command tests engineering behavior;
it cannot provide the existing 252-session warmup or historical research evidence.

For a historical cohort, supply the actual CSV/ZIP files as positional arguments,
with `--corporate-actions path`, `--index path`, `--cohort` symbols or source IDs,
and optional `--output-dir`, `--raw-dir`, `--config-dir`, `--seed`, `--provenance`
or `--calendar` (CSV with a `date` column containing the expected sessions for
the complete requested run). Calendar authenticity is a separate source gate.
Multiple daily inputs are concatenated after normalization and duplicate keys are
rejected. Adjacent acquisition receipts are checked automatically. An explicitly
requested but missing acquisition receipt is an error.

The API is `run_pilot(input_path, *, corporate_actions_path=None, index_path=None,
config_dir=None, output_dir=None, raw_dir=None, source_provenance_path=None,
seed=42, cohort=None, calendar_path=None)`. `input_path` can be one path or a sequence. It returns the
same manifest persisted on disk. No-argument calls retain the old local input
defaults, but those Yahoo-generated inputs do not establish official provenance.
Explicit new inputs never implicitly inherit the old corporate-action/index files.

## Execution and boundaries

1. Normalize and validate source bars while retaining source ISIN-based identity,
   reported turnover, delivery availability and source byte hashes. Group features
   by instrument identity, retaining historical symbols and raw OHLCV.
2. Apply supplied split/bonus factors and compute existing causal features.
   Missing ex-date bars do not discard adjustments. Null/unsupported action types,
   invalid identity fields and nonpositive/nonfinite factors are rejected.
3. Load all four existing YAML configurations. Use configured source turnover,
   coverage and price thresholds to establish universe eligibility as of each
   candidate's detection date. Preserve excluded candidates and their reasons.
4. Compute configured regime context from index history available by that date and
   eligible-cohort breadth. Missing/stale index produces UNKNOWN. Missing VIX and
   breadth inputs are recorded; the configured missing-data policy applies. Regime
   is context, not a new strategy filter absent from the setup definition.
5. Execute DISCOVERY, VALIDATION and HOLDOUT separately with the existing 60/20/20
   allocation and watch-plus-holding gap. Earlier bars warm up features. Events in
   purge gaps do not enter backtests. Outcome bars cannot extend beyond a partition.
6. Retain incomplete WATCH/CONFIRMED records with censor reasons and no terminal R.
   Only uncensored COMPLETED/FAILED outcomes with finite realized R enter snapshots.
   Expired/invalidated candidates remain auditable but are excluded from trade-R
   evidence. Both setup families and all partitions are analyzed separately.

Short datasets can have empty later partitions; no session is reused to fabricate
validation or holdout. A zero-event run publishes typed outputs and explicit
INSUFFICIENT EVIDENCE. Configured transaction costs are applied, including GST on
brokerage, exchange and SEBI charges; the resolved rate is recorded.

Split-adjusted absolute prices use the supplied dataset's basis cutoff, recorded
separately from each evidence partition cutoff. Raw execution prices are retained.
Later split factors rescale earlier absolute adjusted prices; they do not supply
future market-price observations to indicators. Official corporate-action source
reconciliation and broader point-in-time methodology approval remain outstanding.

## Run artifacts

Runs live under `data/processed/pilot_runs/pilot-<fingerprint>-<unique-id>/` by
default. Source, resolved configuration, seed and code hashes determine a stable
fingerprint; each execution preserves its own run identity and directory.

- `features.parquet`: original source fields, raw OHLCV, adjustments and features.
- `universe.parquet`: eligible membership and turnover/coverage statistics for
  candidate detection dates; no claim of a full daily market-universe database.
- `events.parquet`: all detected candidates, universe/partition exclusions and context.
- `outcomes.parquet`: partition labels, censor reasons, evidence eligibility and R.
- `regime.parquet`: available regime context and missing-input flags.
- `statistics.json`: separate setup/partition statistics and dependence limitations.
- `quality.json`: input/run-bound checks, counts, limitations and blocking issues.
- `snapshots/`: hashed outcome Parquet and metadata, including typed empty evidence.
- `manifest.json` plus `manifest.sha256`: trial, methodology, universe/setup versions,
  resolved configuration/costs, input/config/code hashes, boundaries, seed and links
  with hashes for every output and snapshot. The manifest also records missing inputs.

New manifests use schema version 2 and `run-relative-v1` output/snapshot paths.
Absolute paths remain recorded historical metadata; consumers follow verified
relative paths inside the selected run. Copies remain readable without rewriting
frozen files. Older manifests are preserved but need a regenerated run for this
consumer contract.

Snapshot creation rejects future outcome dates and mixed declared partitions.
Loading requires intact outcome bytes even for empty evidence. Existing snapshot
identities cannot be overwritten. Metrics reject pooled partitions and cannot
treat a single OOS row as proof that the whole sample is OOS.

## Quality and consumers

Existing OHLCV validation is reused. The persisted report records source identity,
requested cohort coverage, concurrent symbol ambiguity, observed-session gaps,
relative staleness, setup lookback depth, adjusted-return flags and source availability.
Missing delivery stays null. Short history, cohort gaps/staleness and unavailable
optional data remain visible warnings or UNAVAILABLE checks. A source/identity
failure, missing requested cohort member, missing/unexpected supplied calendar
session, or unexplained adjusted return at or above 50% withholds all evidence.
The 50% threshold is a versioned quality-review trigger, independent of strategy
parameters. Raw inputs and diagnostic outcomes remain preserved; no frozen
snapshots are published for failed-quality runs.

Without an authenticated calendar/history, the report cannot certify calendar
completeness, official corporate actions, identifier continuity or survivorship.
PASSED_WITH_WARNINGS permits engineering inspection only. It never means that
historical pilot admission or paper research is approved.

Launch the dashboard from the repository root:

```bash
.venv/bin/python -m streamlit run src/equity_engine/dashboard/app.py
```

Select the runs folder and a run. `RunEvidence` verifies the selected manifest,
all required output/snapshot bytes, quality binding and snapshot provenance.
Absent quality is UNAVAILABLE; failed or corrupt artifacts cannot yield a valid
quality status. The dashboard shows actual run/partition/source/cutoff information.

Local alert previews never deliver externally:

```bash
.venv/bin/python scripts/preview_run_alerts.py path/to/run/manifest.json --outbox data/processed/preview.sqlite
```

`TelegramAlerter.send_alert(event_id, instrument_id, setup_version, message,
snapshot_id=None, *, manifest_path=..., event_time=source_eod_date, dry_run=True)`
requires a recorded eligible event. An optional explicit snapshot must match;
otherwise the latest matching snapshot with cutoff strictly before the event is
selected. A partition-end snapshot cannot justify its own earlier events.
Run, event, snapshot and delivery-mode identities remain distinct. Dry runs are
recorded as DRY_RUN, never as actual sends, and repeats reverify all evidence.
The separate explicit delivery path is tested with mocks only; no real delivery
is authorized by this milestone.

## Current admission limits

Verified: production orchestration on synthetic acceptance cases and a 20-stock,
single-session official-file smoke check. This is not a completed historical pilot.
Current-run quality/dashboard/dry-run consumers are verified, with retained
examples and 189 passing tests in the 2026-10-20 consumer milestone report.
Historical official coverage, authentic corporate actions/delivery, authenticated
calendar completeness and source reconciliation of abnormal-return flags remain gates.
Regime breadth is the eligible supplied cohort rather than the entire market.
The bootstrap still resamples rows and reports dependence limitations. No paper
research approval or strategy-validity claim follows from this implementation.
