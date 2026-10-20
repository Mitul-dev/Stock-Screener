# PROJECT HANDOFF — INDIAN EQUITY EVIDENCE ENGINE

Prepared: **2026-10-20** (Asia/Calcutta). Intended recipient: another ChatGPT
account using Astra with access to the GitHub repository.

## Start here

You are continuing an existing project. **The current repository is the source
of truth.** Inspect the actual code, configuration and collected tests before
accepting any report. Continue from the implementation; preserve working parts.

- Repository: https://github.com/Mitul-dev/Stock-Screener
- Branch: `main`
- Verified implementation baseline: `9e310ec741c72f5db125f5f0bd4f3ea6bf7f827e`
- That commit contains the project at the **repository root**. There is no extra
  `equity-evidence-engine/` directory inside the GitHub checkout.
- This handoff may be delivered in a subsequent documentation commit. Check the
  current branch and changes after the implementation baseline before acting.

**Current decision: NOT READY FOR REAL-DATA PILOT.**

The official-fixture/ingestion milestone and production-pipeline integration
milestone have been implemented and tested. A genuine historical 20–30-stock
pilot has not been completed. Paper research has not been approved.

Your next intended assignment is **connect evidence consumers to current run
manifests and persisted data-quality results**, then prepare genuine historical
source coverage for the fixed cohort. The concrete scope is below.

If your GitHub access is read-only or cannot execute code, inspect what you can
and deliver concrete findings/patches. State which checks were not executed.
Never claim tests passed because an earlier report or XML says so.

## Project purpose and boundaries

This is a personal-use Indian cash-equity EOD research and alerting engine. It
asks: when a precisely defined technical setup appeared, what happened afterward
under the recorded outcome and cost assumptions?

The intended progression remains:

```text
Genuine NSE historical EOD data
  -> fixed 20–30-stock engineering pilot
  -> data validation
  -> complete V1 pipeline and reproducible evidence
  -> separate paper-research admission decision
```

User constraints:

- Stay within V1. Do not add ML, new strategies, intraday, F&O or BSE scope.
- Keep the existing BREAKOUT_V1 and VCB_V1 strategy thresholds unchanged.
- Do not optimize parameters because signals are rare or results look attractive
  or disappointing. Do not tune against holdout.
- Preserve raw source bytes and earlier experiments/evidence.
- Keep raw OHLCV, adjustment factors and adjusted research prices distinguishable.
- Never invent identifiers, turnover, delivery values or identifier history.
- Missing delivery remains null. A static baseline must remain labelled STATIC.
- Do not equate passing software checks with a validated strategy.
- A correct pilot may have zero setups, losses or INSUFFICIENT EVIDENCE.
- Do not send real Telegram alerts without explicit authorization. Local dry-run
  and mocked tests are sufficient for the next consumer integration milestone.
- Do not approve paper research as a consequence of this handoff.

## Read in this order

1. `BUILD_STATUS.md`
2. `README.md`, `docs/data.md`, `docs/pilot_pipeline.md`
3. `research/reports/production_pipeline_integration_2026-10-20.md`
4. `research/reports/official_fixture_ingestion_2026-10-20.md`
5. Actual source/configuration and current tests listed below.

The older `V1_COMPLETION_REPORT.md`, `V1_AUDIT_REPORT.md`,
`V1_REPAIR_REPORT.md` and September review artifacts are retained history.
Some claim readiness that independent execution disproved; others describe bugs
that later work repaired. They are not current admission decisions. In particular,
the earlier ingestion report's remaining-work section predates the production
integration milestone and is superseded where that work is now implemented.

## Repository map

| Area | Files |
|---|---|
| Ingestion | `src/equity_engine/ingestion/nse_importer.py`, `validator.py` |
| Official acquisition/import commands | `scripts/fetch_official_nse_fixture.py`, `scripts/import_nse_eod.py` |
| Production orchestration | `scripts/run_pilot_pipeline.py` |
| Corporate actions | `src/equity_engine/corporate_actions/adjustor.py` |
| Features | `src/equity_engine/features/calculator.py` |
| Universe | `src/equity_engine/universe/builder.py` |
| Regime | `src/equity_engine/regime/classifier.py` |
| Setups | `src/equity_engine/setups/breakout.py`, `vcb.py` |
| Outcomes | `src/equity_engine/outcomes/engine.py` |
| Research/statistics | `src/equity_engine/backtest/engine.py`, `controls.py` |
| Evidence | `src/equity_engine/evidence/snapshot.py` |
| Consumers | `src/equity_engine/dashboard/app.py`, `alerts/telegram.py` |
| Identity helper | `src/equity_engine/security_master/master.py` |
| Configuration | `config/setups.yaml`, `universe.yaml`, `costs.yaml`, `regime.yaml` |
| Current tests | `tests/unit/`, `tests/integration/`, `tests/leakage/`, `tests/e2e/` |

Python 3.11+, Polars, NumPy, DuckDB, YAML, Streamlit and requests are already used.
Dependencies are declared in `pyproject.toml`. Avoid adding infrastructure or
rebuilding working components merely to implement the next milestone.

## What was implemented and verified

### Genuine official NSE fixture

Retained unchanged file:

`tests/fixtures/nse/BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv.zip`

- Official listing: https://www.nseindia.com/all-reports
- Direct acquisition URL: https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv.zip
- Market date: **2026-10-08**. Actual acquisition date: 2026-10-20.
- Original ZIP size: **208,947 bytes**.
- SHA-256: `07fdfc3409b83fac6ee4a736ceb4fde20069c5d1a490d960b332c178cb703e39`.
- One original CSV member, 3,733 rows total, **2,681 EQ rows**.
- Adjacent `.zip.provenance.json` records source URLs, acquisition timestamp,
  response metadata, original columns, hashes, counts and reference rows.
- All selected EQ rows were independently reconciled to original CSV fields.
- `TtlTrfVal` is the actual source turnover column; it is not reconstructed from
  close multiplied by volume.
- No delivery fields occur in this file. Normalized delivery remains null.

This is authentic-file proof for one current daily schema. It does not establish
legacy historical schema support, authentic delivery parsing, corporate-action
source reconciliation or multi-year historical coverage.

### Repeatable ingestion

- Exact input bytes are archived under `raw_dir/archive/<sha256>/<original-name>`.
- Normalized filenames include input SHA-256 and parser revision.
- Identical input safely reuses its intact output and receipt without rewriting.
- Changed bytes produce separate preserved versions.
- Receipts link input/output hashes, raw source, parser, dates, counts and supplied
  acquisition provenance. Unknown acquisition time is not replaced by import time.
- Raw/output/receipt corruption is rejected. Incomplete artifact pairs fail
  rather than silently replacing evidence.
- Validation precedes normalized publication. HTML, unsupported/malformed input,
  ambiguous multi-CSV archives, invalid OHLCV and invalid required source fields fail.
- Optional absent/blank delivery remains null; supplied delivery bounds are checked.
- Older manifest schemas are preserved; locking prevents lost concurrent appends.

### Actual production integration

- The runner retains source identity, turnover, provenance, raw prices and adjusted
  prices throughout the computation. It no longer creates ticker-shaped ISINs.
- Existing YAML setup/universe/cost/regime configuration is loaded unchanged.
- Universe eligibility is calculated as of each candidate detection date using
  reported turnover, configured coverage and raw-price thresholds. It is not only
  a last-date diagnostic. Excluded candidates and reasons remain auditable.
- Features group by source instrument identity and preserve historical symbols.
- Adjustment handles a missing ex-date bar and rejects invalid factors or repeat
  adjustment. Unsupported/null action identities and supplied action types fail.
- The runner actually calls `ResearchEngine.split_data`, then calls
  `run_backtest` separately on discovery, validation and holdout frames.
- Existing 60/20/20 allocation and watch-plus-holding gap are retained. Small
  datasets have empty later partitions instead of overlapping dates.
- Outcome engines cannot consume bars beyond the active partition end.
- Incomplete WATCH/CONFIRMED outcomes are labelled censored and cannot enter
  frozen trade-R evidence. Terminal COMPLETED and FAILED trades remain eligible.
- Expired/invalidated candidates remain records but do not become trade-R evidence.
- Setup families and partitions are analyzed separately. Controls reject pooled
  partitions and no longer accept one OOS row as proof that all rows are OOS.
- Configured costs are used, including configured GST applied to brokerage,
  exchange and SEBI components.
- Typed empty outputs and explicit no-evidence snapshots make zero-event runs valid.
- Frozen snapshot bytes are required and hashed even for zero rows. Missing,
  corrupt, future-dated or mismatched-partition evidence is rejected. Existing
  snapshot identities cannot be overwritten.

### Run provenance

Each execution preserves a directory under `data/processed/pilot_runs/` by
default. The run includes:

```text
features.parquet
universe.parquet
events.parquet
outcomes.parquet
regime.parquet
statistics.json
snapshots/<id>_meta.json
snapshots/<id>_outcomes.parquet
manifest.json
manifest.sha256
```

The manifest persists trial identity, resolved configuration/costs, setup/universe/
methodology versions, date boundaries, random seed, real source/config/code hashes,
and links/hashes for outputs and snapshots. Run fingerprints are stable for the
same inputs/configuration/code/seed; individual run IDs remain unique. No global
paper-research hypothesis registry is claimed by this engineering run record.

Universe artifacts describe candidate detection dates, not a full NSE membership
database. Regime breadth reflects eligible stocks in the supplied cohort. Missing
index/VIX/breadth availability must remain visible. Regime context does not add a
new setup filter absent from the strategy configuration.

Adjusted absolute prices use a recorded dataset basis cutoff distinct from each
research evidence cutoff. Later split factors rescale earlier adjusted absolute
values. Raw execution values are retained. Do not claim all historical adjusted
absolute prices were knowable on their event date; further corporate-action
source/point-in-time methodology review remains necessary.

## Test evidence and how to reproduce it

Last executed full verification at the implementation baseline:

**135 collected, 135 passed** — 122 cases under `tests/` plus 13 cases from the
original readiness file. One existing Polars String-to-Date deprecation warning
occurs in `csv_provider.py`.

This is historical execution evidence for that commit. Rerun on your checkout.

```powershell
git clone https://github.com/Mitul-dev/Stock-Screener.git
cd Stock-Screener
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[test]"
$env:TELEGRAM_BOT_TOKEN = ""
$env:TELEGRAM_CHAT_ID = ""
.venv\Scripts\python.exe -m pytest tests research/reviews/2026-09-28/test_v1_readiness.py -p no:cacheprovider -q
```

On Linux/macOS use `.venv/bin/python` and the equivalent environment-variable
syntax. Tests use retained fixtures and temporary data; no live Telegram delivery
or NSE download is required. Report actual Python/dependency versions and test
collection. Dependencies are currently not pinned in a lockfile.

Important current suites:

- `tests/integration/test_official_nse.py`: four genuine-file reconciliation cases.
- `tests/integration/test_nse_replay.py`: 19 replay/publication/integrity cases.
- `tests/integration/test_pilot_pipeline.py`: 15 real-entry-point acceptance cases.
- `tests/unit/test_research_partitions.py`: 30 boundary/empty/cost cases.
- `tests/unit/test_pilot_inputs.py`: ten action/universe cases.
- `tests/unit/test_partition_evidence.py`: ten evidence/provenance cases.

The fresh XML committed for that execution is
`research/reports/production_pipeline_tests_2026-10-20.xml`.
Do not count function declarations as test cases; parameterization affects collection.
The older September 17-case review suite was not rerun or rewritten during the
latest milestones and is not claimed to pass the changed runner contract.

The default pytest collection is only `tests/`; it does not automatically include
all historical review scripts. At least one old corporate-action leakage test has
a `pass` body. A green suite therefore remains insufficient proof of every gate.

## Persisted acceptance evidence

Synthetic production inputs and a complete example run are committed under:

`research/reports/production_acceptance_2026-10-20/`

The base synthetic example has 1,200 sessions, 11 candidates, eight evaluated
outcomes, six eligible completed outcomes and two censored discovery records.
Each partition has one completed BREAKOUT and one completed VCB result. Three
illiquid candidates are excluded using source turnover. Six separate snapshots
are produced. Additional automated cases exercise stopped losses, expiry,
invalidation and end-of-data censoring through the production runner.

`research/reports/production_pipeline_verification_2026-10-20.json` links this
example and the genuine-file smoke check. These synthetic outcomes are engineering
acceptance evidence, never official historical strategy evidence.

An actual production smoke check selected 20 stocks from the genuine one-day NSE
fixture. It preserved 20 distinct source IDs and completed with zero events and
INSUFFICIENT EVIDENCE. There was one discovery session and no validation/holdout
sessions. This proves handling of the genuine input and short history only.

The smoke cohort was:

```text
RELIANCE TCS HDFCBANK INFY ICICIBANK HINDUNILVR ITC SBIN BHARTIARTL KOTAKBANK
LT ASIANPAINT AXISBANK MARUTI SUNPHARMA TITAN BAJFINANCE TATASTEEL ULTRACEMCO WIPRO
```

Reproduce a short genuine-file run with:

```powershell
.venv\Scripts\python.exe scripts/run_pilot_pipeline.py tests/fixtures/nse/BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv.zip --cohort RELIANCE TCS HDFCBANK INFY ICICIBANK HINDUNILVR ITC SBIN BHARTIARTL KOTAKBANK LT ASIANPAINT AXISBANK MARUTI SUNPHARMA TITAN BAJFINANCE TATASTEEL ULTRACEMCO WIPRO
```

No corporate-action/index source is supplied in that smoke command; warnings are
expected. Do not label that history action-free or its regime verified.

## Known gaps — do not claim these are solved

### 1. Dashboard consumption and honest data-quality status

`src/equity_engine/dashboard/app.py` still reads the old fixed path
`data/processed/pilot_outcomes.parquet`. The new runner writes isolated run folders.
The dashboard still sets Data Quality to VALIDATED merely because a nonempty
outcome file exists. This is a concrete remaining defect.

It should load a selected current run manifest, resolve and verify its artifacts,
show actual run/partition/source/cutoff information, and show unavailable or failed
quality status when quality results are missing or failed. Outcome count must not
be used as a substitute for data validation. UI polish is not required.

### 2. Persisted pilot data-quality results

Importer validation is useful but does not establish calendar completeness,
stale-history acceptability, abnormal-return explanations, corporate-action
reconciliation, source completeness or identifier continuity.

Implement explicit persisted checks and counts that the run and consumers can
reference. Distinguish warnings, unavailable optional data and blocking failures.
Do not turn missing delivery or legitimate no-setup runs into fabricated values
or arbitrary failures. Suspicious returns should be flagged/reconciled without
changing the strategy. Fail or withhold evidence when critical checks fail.

### 3. Run-scoped alert eligibility

`TelegramAlerter.send_alert` now accepts an explicit `snapshot_id`, rejects missing
or corrupt evidence, appends frozen statistics/limitations, and retains outbox
idempotency. Those repairs exist; do not describe alerts as accepting missing
evidence anymore.

What remains is actual consumer wiring and verification: select the correct
run-scoped frozen snapshot, verify setup/version and event-time/cutoff eligibility,
and reject mismatches. The event ID and snapshot ID are different identities.
Use dry-run/mocked delivery; do not send actual notifications.

### 4. Genuine historical cohort and sources

One authentic daily fixture is not several years of history. The actual fixed
20–30-stock historical engineering cohort still needs sufficient warmup,
evaluation partitions and follow-up, with original source provenance.

Reconcile authentic corporate actions, source dates/ex-dates, identifier changes,
actual turnover and delivery availability. Do not assume current schemas cover
all historical formats. Legacy parsing exists but lacks genuine legacy-fixture
proof. `SecurityMaster` exists, but end-to-end official identity-history integration
and survivorship completeness must not be inferred from that class alone.

`scripts/fetch_pilot_data.py` is an older Yahoo-derived simulation with fabricated
NSE-like fields. `scripts/fetch_nifty.py` also uses Yahoo. They do not close official
NSE source gates. Use the new official acquisition/import path where supported.

### 5. Statistical/paper-research admission

Current metrics use a deterministic row bootstrap and a STATIC hurdle. Families
and partitions remain separate. The small-sample/OOS checks have improved, but
an existing rule can still label a sufficiently positive pure-OOS sample with at
least five distinct detection dates VALIDATED. That rule is not an independently
approved adequate-sample/dependence methodology.

`effective_n` currently represents observation count; it is not a demonstrated
dependence-adjusted sample size. Overlapping holdings and market clustering remain
limitations. Do not call the baseline matched controls or claim profitability,
calibrated probabilities, survivorship safety or a production-ready trading tool.
The engineering runner's aggregate status is EXPERIMENTAL or INSUFFICIENT EVIDENCE,
and its manifest explicitly does not approve paper research.

## Recommended next implementation milestone

Complete a small, reviewable **current-run quality and evidence-consumer path**:

1. Inspect dashboard, alerts, snapshot loader, run manifest structure and current
   validator. Rerun relevant baseline tests before changes.
2. Define and persist a quality result tied to the actual run/input hashes, with
   check names, counts, status, limitations and blocking issues. Reuse existing
   validation rather than introducing a parallel engine.
3. Make the dashboard select/load a run and show its recorded quality and evidence.
   Stop reading the legacy output as if it were the current run.
4. Bind dry-run alerts to the appropriate frozen setup/version evidence and quality
   result. Verify identity, integrity and event-time eligibility explicitly.
5. Add meaningful integration tests for a valid run, no events, absent/failed quality,
   missing/corrupt artifacts, setup/version mismatch, future evidence and repeat
   alert idempotency. Exercise consumers with actual frozen files.
6. Run the relevant tests and full suite, update BUILD_STATUS and a concise milestone
   report with actual results and remaining gates. Preserve previous evidence.

After that, proceed to genuine historical cohort acquisition/validation. Keep
configuration and strategy parameters fixed while measuring data/pipeline behavior.

## Portability and repository caveats

- `data/raw/`, `data/processed/`, virtual environments, real environment files,
  packaging metadata, caches and runtime lock files are ignored by Git.
- The official source fixture and its acquisition receipt are committed under
  `tests/fixtures/nse/`. They are available to the new account through the repo.
- The genuine one-day smoke run under `data/processed/...` was local and is not in
  a clean clone; the committed report/summary describes it, and it can be regenerated.
- The committed synthetic acceptance bundle contains example outputs/receipts.
- Existing reports/manifests contain absolute Windows paths from the original
  machine. Those paths do not grant access from another account. Resolve the
  corresponding committed artifact by its repository-relative location, or generate
  a new run locally. Do not require that old Windows directory to exist.
- Do not rewrite frozen metadata just to replace local paths: that changes hashes.
  Design any new portable path contract as an explicit versioned improvement.
- `.gitattributes` preserves original bytes. Avoid automatic line-ending conversion,
  fixture repacking or mass formatting that invalidates recorded source/evidence hashes.
- The local full-suite test command used normal Windows filesystem access because
  a restricted execution sandbox denied atomic link/rename operations. This was an
  environment restriction, not a reason to remove atomic publication safeguards.
- The committed `.env.example` contains placeholders. Credentials are not needed
  to run the offline verification suite.

## What to return after your work

Report the concrete behavior changed, files touched, actual commands/test collection,
failures, any unexecuted checks and the remaining gates. Link the evidence.
Keep the distinction between software integration, genuine source coverage,
engineering pilot admission and paper-research approval explicit.

Do not repeat old READY claims. Change the readiness decision only when the actual
critical gates have been independently verified against the current implementation.
