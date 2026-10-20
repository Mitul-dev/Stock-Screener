# Independent V1 repair verification — 2026-09-29

**Decision: NOT READY FOR REAL-DATA PILOT**

**OFFICIAL DATA GATE: NOT YET VERIFIED**

The current implementation contains useful repairs, but the claim that all critical integration gates are complete is contradicted by fresh execution. Paper research is not approved.

## Scope and preservation

Inspected the repository inventory, README, BUILD_STATUS, completion/audit/repair reports, configuration, source components, relevant unit/leakage/E2E tests, both review suites, data files and acquisition script. The attached handoff defines the requirements; its implementation claims were not treated as evidence.

No application source, existing tests, strategy parameters or data were edited by this review. The SHA-256 comparison of the pre-review source/configuration/test/data inventory found **zero changes**. New review artifacts are in this directory. Running the existing gate tests regenerates their two JSON summaries; their pre-run versions were copied here as `before_*.json`. Temporary market inputs and alert databases were isolated and removed after execution. No external alerts were sent.

## Fresh test results

| Invocation | Collected | Passed | Failed |
|---|---:|---:|---:|
| `.venv\\Scripts\\python.exe -m pytest -p no:cacheprovider` | 26 | 24 | 2 |
| `.venv\\Scripts\\python.exe -m pytest research/reviews/2026-09-28/reverification/test_pipeline_gates.py -v` | 17 | 17 | 0 |
| `.venv\\Scripts\\python.exe -m pytest research/reviews/2026-09-28/test_v1_readiness.py -p no:cacheprovider -v` | 13 | 13 | 0 |

The main-suite failures are `test_outcome_engine` and `test_research_engine_backtest`. They expect a stopped trade to be COMPLETED; current code returns FAILED. That may be the intended new state contract, but the tests have not been reconciled with it. The claim “pytest = PASS” is false for this repository state. This mismatch alone does not establish that stop-price arithmetic is wrong.

Logs: [main suite](<C:/Users/mitul/Downloads/Stock Screener/equity-evidence-engine/research/reviews/2026-09-29/existing_suite.txt>), [17 gate tests](<C:/Users/mitul/Downloads/Stock Screener/equity-evidence-engine/research/reviews/2026-09-29/pipeline_gates.txt>), [13 readiness cases](<C:/Users/mitul/Downloads/Stock Screener/equity-evidence-engine/research/reviews/2026-09-29/readiness_rerun.txt>).

**13 versus 11 resolved:** `test_v1_readiness.py` contains 11 test functions. Its first function has three parameter combinations, giving 13 collected cases. This is not evidence that a different file was run. All 13 passed now. The pre-existing `readiness_checks.xml` records 13 tests and **11 failures**; it is an old failing artifact, not proof of current passes.

## 1. Official ingestion and publication — critical gate unverified/failed

No genuine official NSE EOD fixture with original bytes and verifiable official provenance was found. The existing `NSE_Pilot_Bhavcopy.csv` is supported by a Yahoo acquisition script that explicitly simulates the new NSE format, fabricates ISINs/trade counts, and estimates turnover as close × volume. A manifest hash of those bytes does not establish official origin. The ZIP gate generates its own synthetic CSV archive. It proves generic ZIP mechanics only.

[Acquisition script](<C:/Users/mitul/Downloads/Stock Screener/equity-evidence-engine/scripts/fetch_pilot_data.py>) and [importer](<C:/Users/mitul/Downloads/Stock Screener/equity-evidence-engine/src/equity_engine/ingestion/nse_importer.py>) show:

- Genuine improvement: ZIP input is read, schema routing exists, optional delivery columns can be preserved, and DataValidator runs before Parquet publication. Synthetic HTML and invalid-OHLC inputs were rejected by the passing gates. Duplicate checks use instrument/date, and the synthetic market date is retained.
- ZIP selection takes the first lowercase `.csv` member. No dedicated corporate-action/PR archive parser exists in this importer, despite the repair report's broader claim.
- Official schema compatibility, authentic identifiers, actual turnover, delivery fields and official source-date semantics remain unverified.
- The importer records the basename, byte hash, size, parser and minimum row date. “downloaded_at” is import time; original download URL/time and immutable original-byte retention are not established.
- A changed file at the same input filename silently overwrote the same normalized Parquet path in a temporary reproduction. Both hashes are recorded in `observations.json`. Strict processed-file immutability is not implemented. The acquisition script also writes fixed raw filenames.
- Validation covers OHLCV and duplicate keys; it does not establish security identity, missing-session policy, delivery/turnover validity or abnormal-return/corporate-action reconciliation.

The real runner additionally discards source identifiers, turnover, delivery and provenance when selecting adjustment inputs, then manufactures `INE{symbol}01010`. See [runner identity construction](<C:/Users/mitul/Downloads/Stock Screener/equity-evidence-engine/scripts/run_pilot_pipeline.py:54>).

## 2. Corporate-action chain — failed

Features and outcomes now choose adjusted columns when present. Raw OHLCV and `adj_*` remain separate in the feature frame. However, [BREAKOUT detection](<C:/Users/mitul/Downloads/Stock Screener/equity-evidence-engine/src/equity_engine/setups/breakout.py:48>) compares raw close against an adjusted 252-session high. [VCB detection](<C:/Users/mitul/Downloads/Stock Screener/equity-evidence-engine/src/equity_engine/setups/vcb.py:18>) builds its breakout level from raw highs while outcomes compare adjusted closes against that level.

Concrete unchanged-parameter 2:1 split probes:

| Scenario | Actual result | Consistent adjusted-basis reference |
|---|---|---|
| BREAKOUT candidate before split during WATCH | Raw close 94 is compared with adjusted high 50.5; emits a false WATCH candidate | Adjusted close 47 is below the near-high requirement; no candidate |
| VCB event 2020-12-30, split 2020-12-31 | Raw level 100.5 versus adjusted close 50.375; EXPIRED | Level 50.25; confirmed 2020-12-30 and COMPLETED |
| BREAKOUT split 2021-01-13 during holding | COMPLETED; net R -0.1683577412, MFE 0.3294117647, MAE -0.3294117647 | Same values |

The holding-period fix works for the tested BREAKOUT path. The false WATCH candidate did **not** falsely confirm; the corrected outcome comparison prevented that. These successes do not repair detector basis mixing.

Already-adjusted provider OHLCV is not guarded: reapplying the same split to adjusted prices, even with a `price_basis=adjusted` column, changed the pre-split adjusted close from 50 to 25 while post-split close stayed 50. There was no rejection. This concerns adjusted provider values supplied as OHLCV, not simply recomputing `adj_*` from unchanged raw columns.

Outcome artifacts expose generic entry/exit prices without a price-basis marker or corresponding raw execution values. The raw/adjusted distinction is therefore incomplete downstream.

## 3. Nonvacuous end-to-end path — partially verified

The real production runner was executed with six synthetic instruments and existing strategy parameters. Instrumentation wrapped and delegated to the actual implementations of all three requested methods.

Observed **6 events**: **2 COMPLETED**, **1 FAILED**, **1 EXPIRED**, **1 INVALIDATED**, **1 censored WATCH**. The component acceptance path also independently exercised BREAKOUT WATCH → CONFIRMED → COMPLETED. Both BREAKOUT and VCB produced research metrics and reloadable evidence snapshots. Touch-label columns exist, with a positive 1R touch in the VCB fixture. This is not a zero-completed-events pass.

Observed production calls: **split_data once, run_backtest once, create_snapshot twice**. The one backtest received **all 340 sessions and all six events**, not the returned partitions. The two snapshots correctly separate setup families and retain stopped trades in production statistics.

The runner's UniverseBuilder uses zero eligibility thresholds, computes only the last-date universe, and never uses that result to filter events. Regime is likewise computed with a permissive override and unused. Reported turnover is discarded, causing the universe helper to fall back to close × volume. Existing point-in-time helper tests therefore do not prove the production universe path.

## 4. Chronological execution and crossing outcomes — failed

[Runner split/backtest calls](<C:/Users/mitul/Downloads/Stock Screener/equity-evidence-engine/scripts/run_pilot_pipeline.py:109>) computes DISCOVERY/VALIDATION/HOLDOUT, then ignores all three frames and backtests the full history. No partition-specific evidence is produced.

In the 340-session run, snapshots declare **data_cutoff 2020-10-13** but contain events detected **2020-12-30** and outcomes ending **2021-01-27/28**. This is future evidence relative to the claimed cutoff. These artifacts are whole-history aggregates, not holdout evidence; no holdout result was verified.

Two actual-runner counterexamples were reproduced:

1. **Purged-gap event:** detection 2021-05-20 lies after discovery end 2021-05-19 and before validation start 2021-06-23. It should not enter any returned partition. The runner nevertheless evaluates it through an exit on 2021-06-23 and freezes it under the discovery cutoff.
2. **Discovery event crossing validation:** detection is exactly discovery end **2021-05-19**. One instrument lacks 20 subsequent sessions while a second instrument supplies the full market calendar. The runner accepts this data. The 20-bar holding outcome exits **2021-07-20**, after validation starts **2021-06-23**, and is included in the snapshot with cutoff 2021-05-19.

The helper's fixed market-session gap does not handle missing instrument sessions or perform event-level censoring. The production path neither rejects this data nor purges/censors the crossing outcome.

## 5. Trial registry and reproducibility — failed

Actual generated metadata contains setup/universe/methodology version strings, seed 42 and snapshot UUIDs. Snapshots can be reloaded.

But production persists `configuration={}`, `cost_model={}`, only `discovery_end`, `input_hash="pilot-input"` and `output_hash="pilot-output"`. These are placeholders, not reproducibility. There is no trial ID, full boundary set, run manifest linking inputs/configuration/outcomes/snapshots, or implemented trial registry. The comment “Commit to registry” precedes only snapshot creation. The runner discards returned snapshot IDs and overwrites the same outcomes path.

[Snapshot creation arguments](<C:/Users/mitul/Downloads/Stock Screener/equity-evidence-engine/scripts/run_pilot_pipeline.py:130>) and [snapshot implementation](<C:/Users/mitul/Downloads/Stock Screener/equity-evidence-engine/src/equity_engine/evidence/snapshot.py>) do not calculate or verify evidence hashes. Configured cost YAML is not loaded by the runner.

## 6. Statistical safeguards — partially verified, critical validation gate failed

Verified: N=1 returns INSUFFICIENT EVIDENCE; mixed setup families raise; production groups families; default baseline is explicitly STATIC; independent five-observation bootstrap reruns with seed 123 produced identical statistics and CI [-0.4, 1.34].

Counterexample: **two +1R observations on the same date**, with no out-of-sample evidence, returned **VALIDATED**, CI [1, 1], `effective_n=2`, `distinct_time_blocks=1`. [ControlEngine status decision](<C:/Users/mitul/Downloads/Stock Screener/equity-evidence-engine/src/equity_engine/backtest/controls.py:39>) has no out-of-sample or adequate-sample gate. “effective_n” is the raw observation count.

A dependence warning is persisted and printed by the runner, so a CLI user can see it. It is absent from the dashboard and alert evidence text. The bootstrap resamples individual rows, despite the warning's reference to independent detection blocks.

## 7. Dashboard, frozen evidence and forward identity — partially verified/failed

Runtime capture of the overview returned Market Regime **UPTREND**, Detected Setups **5**, Data Quality **UNKNOWN**. The first two remain hardcoded. Changing VALID to UNKNOWN only repairs one label.

Snapshot loading itself works. Telegram attempts `load_snapshot(alert_id)`, but silently ignores every loading error. A missing-snapshot alert was accepted and written to the local test outbox with caller text alone. Supplying an actual snapshot UUID successfully appended its statistics. There is no explicit event-to-evidence association: deterministic event IDs and random snapshot UUIDs occupy different identity spaces. The missing-evidence path continues toward delivery in normal code as well; network delivery was not exercised.

Identical SetupEvent arguments now produce identical event IDs. This component repair is confirmed, but it does not supply the missing frozen-evidence linkage.

## Why 17/17 did not establish readiness

The current tests pass the assertions they contain. Several assertions are narrower than the claimed gates:

- Production test checks split/snapshot calls, but not partition use or backtest inputs.
- Metadata test checks key presence, allowing empty dictionaries and placeholder hashes.
- ZIP fixture is synthetic.
- Split test checks one absence of false confirmation, not detector equivalence or split-during-WATCH VCB behavior.
- Chronology test calls a helper on dense data, not production enforcement with missing sessions.
- Bootstrap test now uses the single completed BREAKOUT observation, which bypasses resampling.
- Dashboard test only rejects the tuple Data Quality/VALID.
- Telegram test only checks that a mocked loader was called; unpacking its mock can fail and be swallowed.
- The default suite also contains a corporate-action leakage test whose body is `pass`, and a synthetic E2E test whose statistics assertion is conditional on any completed outcomes.

## Required repair order before reassessment

1. Preserve one genuine official NSE EOD fixture with original bytes, source provenance and hash; prove its real schema/fields and archive behavior. Preserve authentic identifiers and turnover through production.
2. Establish one research price basis across both detectors/outcomes, retain raw execution traceability and reject unsupported/double-adjusted inputs. Keep strategy thresholds unchanged.
3. Wire the configured point-in-time universe and actual chronological partitions into the runner. Enforce event-level censoring/purging, including sparse histories; ensure snapshot cutoff covers only allowed evidence.
4. Persist real trial/configuration/cost/boundary/hash records and link all artifacts to the run.
5. Prevent VALIDATED without adequate, appropriately independent out-of-sample evidence. Expose statistical limitations where evidence is shown.
6. Require a resolvable frozen snapshot for alerts, remove remaining fabricated dashboard values, and reconcile the stop-state contract with tests.
7. Strengthen gate assertions around the concrete counterexamples, rerun the full suite, and request independent reassessment.

These are V1 integration repairs. No ML, new setups or strategy optimization is required.

## Reproduction artifacts

[Diagnostic runner](<C:/Users/mitul/Downloads/Stock Screener/equity-evidence-engine/research/reviews/2026-09-29/verify_remaining_gates.py>) uses existing implementations with temporary synthetic inputs. [Recorded observations](<C:/Users/mitul/Downloads/Stock Screener/equity-evidence-engine/research/reviews/2026-09-29/observations.json>) contains production call arguments, boundaries, outcomes, reloaded snapshot metadata, split comparisons, statistical counterexamples, alert messages and preservation results. [Pre-review hashes](<C:/Users/mitul/Downloads/Stock Screener/equity-evidence-engine/research/reviews/2026-09-29/source_snapshot.json>) identifies the reviewed source state.

Run from the repository: `.venv\\Scripts\\python.exe research/reviews/2026-09-29/verify_remaining_gates.py`.

