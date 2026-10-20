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
and optional `--output-dir`, `--raw-dir`, `--config-dir`, `--seed` or `--provenance`.
Multiple daily inputs are concatenated after normalization and duplicate keys are
rejected. Adjacent acquisition receipts are checked automatically. An explicitly
requested but missing acquisition receipt is an error.

The API is `run_pilot(input_path, *, corporate_actions_path=None, index_path=None,
config_dir=None, output_dir=None, raw_dir=None, source_provenance_path=None,
seed=42, cohort=None)`. `input_path` can be one path or a sequence. It returns the
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
- `snapshots/`: hashed outcome Parquet and metadata, including typed empty evidence.
- `manifest.json` plus `manifest.sha256`: trial, methodology, universe/setup versions,
  resolved configuration/costs, input/config/code hashes, boundaries, seed and links
  with hashes for every output and snapshot. The manifest also records missing inputs.

Snapshot creation rejects future outcome dates and mixed declared partitions.
Loading requires intact outcome bytes even for empty evidence. Existing snapshot
identities cannot be overwritten. Metrics reject pooled partitions and cannot
treat a single OOS row as proof that the whole sample is OOS.

## Current admission limits

Verified: production orchestration on synthetic acceptance cases and a 20-stock,
single-session official-file smoke check. This is not a completed historical pilot.
Historical official coverage, authentic corporate actions/delivery, calendar and
abnormal-return checks, and current-run dashboard/alert integration remain gates.
Regime breadth is the eligible supplied cohort rather than the entire market.
The bootstrap still resamples rows and reports dependence limitations. No paper
research approval or strategy-validity claim follows from this implementation.
