# Independent verification of reported V1 repairs

Decision: **NOT READY FOR REAL-DATA PILOT**

This decision concerns the user's seven pilot-readiness gates. Paper research is not approved. No source code, strategy thresholds, configurations, original data, or prior test files were changed during this verification. Only separate review artifacts were added. No ML or new strategies were added. No Telegram messages were sent.

## Claims checked by actual execution

| Claim | Independent result |
| --- | --- |
| 26/26 existing tests pass | Confirmed: all 26 passed |
| 13/13 readiness tests pass | Confirmed: all 13 collected cases passed |
| Only 11 tests appear in the list | There are 11 test functions; one has three parameter cases, producing 13 collected cases |
| Existing readiness XML proves the latest result | False: it is the old result, with 13 cases and 11 failures |
| V1 repairs completed | Partial repairs verified; substantial integration gates still fail |
| Ready for real-data pilot | Not supported by the seven gates |

The readiness count is **10 unparametrized functions + 3 cases of one parametrized function = 13 cases**. The three cases are null open, infinite volume, and zero close. No second readiness file is needed to explain the count. We cannot reconstruct the implementation owner's unrecorded command, but independent collection/execution of the named file now confirms the 13-pass claim. The old XML must not be presented as that execution's evidence.

Commands executed from the existing project root with its `.venv`:

```powershell
$env:TELEGRAM_BOT_TOKEN = ''
$env:TELEGRAM_CHAT_ID = ''
.\.venv\Scripts\python.exe -m pytest --collect-only -q research/reviews/2026-09-28/test_v1_readiness.py -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests research/reviews/2026-09-28/test_v1_readiness.py -p no:cacheprovider --junitxml=research/reviews/2026-09-28/reverification/baseline_and_readiness.xml
.\.venv\Scripts\python.exe -m pytest research/reviews/2026-09-28/reverification/test_pipeline_gates.py -p no:cacheprovider --junitxml=research/reviews/2026-09-28/reverification/pipeline_gates.xml
```

- Original/readiness run: **39 passed, 1 warning**, 5.86 seconds. The warning is the existing Polars String-to-Date deprecation.
- Broader gate run: **14 failed, 3 passed**, 1.97 seconds. No skips or expected-failure markers.
- All 17 new cases are independent acceptance probes, outside the default test collection. Several probe proposed output contracts (for example target-label and trial-field names); the underlying absence is also confirmed by reading the implementation. These probes do not prescribe a redesign.
- Source hashes were unchanged between the beginning and end of verification. Original raw and processed data hashes still match the prior review.

## Gate 1 — Official-data boundary: FAIL

No genuine official NSE fixture or source-authenticated importer test was found in the repository. The only CSV/ZIP/GZ candidates under existing tests/data/research were the old Yahoo-derived pilot files and their manifest. The raw pilot still uses generated ISINs and estimated turnover; its original hash is unchanged. The readiness delivery test uses a constructed one-row DataFrame. This proves a narrow column-handling repair, not exchange-format compatibility.

| Boundary requirement | Verified behavior |
| --- | --- |
| Genuine official fixture | Not evidenced; cannot approve compatibility from synthetic headers |
| ZIP | Synthetic CSV-in-ZIP fails with `ComputeError: invalid utf-8 sequence` at `nse_importer.py:39`; no archive handling |
| Schema detection | Only two header heuristics, followed by assumed column names; no genuine schema/version fixture |
| Identifiers | Input `ISIN` is copied directly; `TEST_*` IDs in the synthetic fixture are accepted; no authentic identity validation/resolution |
| Actual turnover | A supplied field is copied, but authenticity/units are not verified; the old fetcher manufactures close × volume |
| Delivery | Consolidated optional-column bug is fixed and readiness test passes; official delivery-file join and range validation are not established; legacy parser omits canonical optional null columns |
| Source dates | Bar dates are parsed, but a synthetic 2020-01-01 file is manifested as 2026-09-28 |
| Provenance | File hash/size recorded; download time is actually import time; no canonical `source_file`/`source_date`, source URL, or source-authenticated fixture |
| Immutable raw storage | Importer reads inputs without modifying their bytes, but does not create/enforce an immutable acquisition store; unchanged fetch scripts overwrite raw filenames |
| HTML rejection | PASS for tested HTML page, with no processed Parquet written |
| Malformed market data | FAIL: negative open is persisted as processed because importer never invokes validation |

`DataValidator` now rejects null/nonfinite prices/volume and zero prices, and handles instrument/date duplicates. These are real improvements. The production importer still publishes before validation, and `run_pilot_pipeline.py:29` still catches validation failures and continues.

The review did not download a new official fixture or claim that a synthetic fixture is official. The official-data gate fails because the required evidence is absent and basic boundary behavior fails locally.

## Gate 2 — Corporate-action integration: FAIL

The simple split arithmetic still works. `FeatureCalculator` now uses `adj_*` values for indicators, which makes the original readiness split-feature check pass. However, it leaves the raw OHLCV columns in the returned frame. `BreakoutDetector` compares raw `close` with adjusted `high_252d`; `VCBDetector` calculates its consolidation high and compares close on raw columns while ATR is adjusted. `OutcomeEngine` confirms/enters/exits using raw prices but uses an adjusted event level/ATR.

The new 310-session example contains a genuine synthetic 2:1 price/volume discontinuity at session 290 and a WATCH candidate at session 260. On that candidate:

- Raw close: **100**.
- Adjusted close: **50**.
- Adjusted breakout level: **50.5**.
- A consistently adjusted reference has **no confirmation**.
- The actual composition confirms on **2020-12-30**, because it compares raw 100 with adjusted 50.5.

This is an executed counterexample through adjustment → features → detector → outcome, not merely a suspicion from source inspection. No threshold was modified. Full-history future adjustments additionally require an explicit as-of/basis policy; the above mismatch cannot be dismissed as a harmless uniform rescaling.

There is still no input price-basis contract or guard proving an already-adjusted provider history will not be adjusted again. The Yahoo fetcher's `auto_adjust=False` comment is not evidence of compatibility with this adjustment pipeline. End-to-end absence of double adjustment is therefore unproven.

## Gate 3 — Full end-to-end research path: FAIL, with useful component progress

A new synthetic fixture uses the **unchanged setup YAML** and normal default outcome settings, with 340 weekday sessions for five synthetic instruments. Prices/volume, rather than strategy thresholds, create the test conditions. No handwritten indicator values are used in this chain.

The review harness executes CSV importer → adjustment → features → both detectors → `ResearchEngine.run_backtest` → per-family metrics → snapshot save/load. It proves:

| Required observation | Actual result |
| --- | --- |
| BREAKOUT WATCH | WATCH with history ending at detection |
| BREAKOUT CONFIRMED | CONFIRMED with history ending at confirmation |
| BREAKOUT COMPLETED | COMPLETED with the full outcome window |
| VCB event/outcome | One VCB event and one completed VCB outcome |
| Unconfirmed failure | One EXPIRED |
| Nonpositive-risk failure | One INVALIDATED |
| Censored setup | One WATCH at dataset end |
| Explicit FAILED state | Not emitted; enum exists without an implemented failure rule |
| Outcomes | Exactly two completed outcomes; gross/net R and excursions present |
| +1R and +2R touch labels | Neither is emitted; optional single `target_r` exit is not both labels |
| Research result | Per-family descriptive metrics produced by the review harness |
| Evidence snapshot | Two component snapshots created and reloaded with exact frame equality |

An expired or invalidated setup should not be relabeled FAILED just to pass a test. The implementation needs a defined failure policy if FAILED is required, and must document the distinction. Even if expiration is accepted as the intended failed-setup behavior, the other gate failures independently block readiness.

The **actual production pilot script** was also run against these synthetic files in a temporary directory, with passive method spies that preserve behavior. It produced the same five final states (2 COMPLETED, 1 EXPIRED, 1 INVALIDATED, 1 WATCH), but made **zero calls to `ResearchEngine.split_data` and zero calls to `EvidenceSnapshot.create_snapshot`**. Its metrics pool both setup families. This distinguishes a working manually assembled component chain from an integrated production research path.

The original E2E test remains vacuous for outcomes/statistics: a fresh instrumented run yields **47 EXPIRED + 1 WATCH, zero COMPLETED**. Its conditional `if outcomes:` still skips statistics. None of the new non-vacuous assertions has been substituted into the original passing test.

## Gate 4 — Chronological research execution: FAIL

`ResearchEngine.split_data` now inserts a gap, but it adds **calendar days**, while WATCH/holding windows count available trading rows. It does not inspect event confirmation/exit dates, purge discovery events whose outcomes cross into validation, or label censored boundary outcomes. The production pilot never calls it.

A 400-weekday-session counterexample uses the actual split helper and actual outcome engine:

- Discovery detection: **2020-12-02**.
- Validation starts: **2020-12-28**.
- The discovery event exits: **2021-01-05**.

The inserted gap is shorter than the WATCH plus holding period in trading sessions, so the event overlaps validation. `run_backtest` accepts full history and does not enforce partition ownership. A caller can truncate inputs manually, but no production orchestration does so. Actual DISCOVERY → VALIDATION → HOLDOUT execution, including boundary handling, is not established. The updated unit test increased input length from 100 to 1,000 days and checks only nonempty ordered date sets; it does not prove outcome isolation.

## Gate 5 — Trial and reproducibility: FAIL

No trial registry implementation or invocation was found. Snapshot roundtrip works and records methodology/universe/setup version, data cutoff, creation time, ID, and statistics. It does **not** record the full configuration, cost model, chronological boundaries, input hash, random seed, or output/evidence hash. The importer hash is not linked to a research trial/snapshot. The random seed argument to metrics is not persisted in returned statistics or snapshot metadata.

The cost YAML still uses `costs` while `OutcomeEngine` expects `transaction_costs`; the pilot loads neither and uses defaults. A declared reproducible cost model cannot be inferred from the mere presence of that YAML file.

The hashes written by this independent review identify what was inspected. They are not represented as application trial-registry functionality.

## Gate 6 — Statistical safeguards: FAIL, with partial fixes confirmed

- **PASS:** N=1 now returns `INSUFFICIENT EVIDENCE`.
- **PASS:** Equal input and seed reproduce identical bootstrap output.
- **PASS:** The default baseline is explicitly `STATIC`; no matched-control claim is required to run it.
- **FAIL:** The actual pilot pools both families; direct mixed-family aggregation also silently returns one result. Manual grouping in the review harness does not repair production integration.
- **FAIL:** Dependence limitations are not returned in metrics or snapshots. Raw count is still named `effective_n`, and unique detection dates are called blocks without a holding-period dependence model. A code comment about dependence is not a user-visible limitation.
- **FAIL:** Two +1R events on the same date already return `VALIDATED`, with no partition or out-of-sample proof supplied. The N=1 repair is narrow.
- **FAIL:** No executed holdout result exists in the production pilot. Its whole-history output has no partition provenance. This review does not allege that it literally emits a `HOLDOUT` label; it does show that nothing in `VALIDATED` establishes holdout evidence.

## Gate 7 — Dashboard and alert integration: FAIL

- `dashboard/app.py:26–28` still renders hardcoded **UPTREND / 5 / VALID**, confirmed by executing `render_overview` with a capture-only display stub.
- The standalone evidence snapshot **can** be loaded, as proven by exact roundtrip of both synthetic setup outcome frames.
- `TelegramAlerter.send_alert` accepts arbitrary caller text and does not load frozen evidence. No production caller that prepares alerts from snapshots was found. A local test-mode send succeeded without any snapshot read. No network message was sent.
- Identical forward event construction yields different IDs because `SetupEvent` uses `uuid.uuid4()`. A duplicate caller-supplied Telegram ID test does not prove deterministic forward-event identity.

## Required repairs before reevaluation

1. Test the importer against an authentic official file with retained source provenance; implement ZIP handling, validation before publication, canonical source dates and immutable acquisition. Preserve null delivery when unavailable.
2. Establish one explicit research price basis through features, detection and outcomes while retaining raw execution data separately. Prove split/bonus transitions during both WATCH and holding periods and reject incompatible/double-adjusted inputs.
3. Integrate a non-vacuous runner using the existing YAML configurations, dated security identity and universe/regime context. Emit required target labels and explicit failure/censoring semantics.
4. Execute chronological partitions with session-aware, outcome-aware purge/censor rules. Add a trial registry linking input/configuration/cost/seed/version/boundary hashes to per-family results and evidence hashes.
5. Keep family analysis separate, expose dependence limitations, and tie any validated status to the required evidence stage. Replace hardcoded dashboard status, connect alerts to frozen snapshots and make forward-event identity deterministic.
6. Rerun original tests, the unchanged 13 readiness cases, and the broader gate cases. Replace stale reports with generated run evidence without treating this exploratory history as untouched holdout.

These are V1 integration repairs. They require no strategy tuning, new setup family or ML.

## Saved evidence

All paths below are relative to this review directory:

- `baseline_and_readiness.xml`: fresh 39-pass execution, with individual test identities.
- `pipeline_gates.xml`: 17 new cases, 14 failures and 3 passes.
- `test_pipeline_gates.py`: reproducible tests and synthetic fixture; no authentic-data claim.
- `component_chain.json`: non-vacuous component-chain states, per-family results and loaded metadata.
- `pilot_execution.json`: production pilot states and observed split/snapshot call counts.
- `boundary_observations.json`: original E2E state counts, N=1/N=2 behavior and unchanged-file verification.
- `source_snapshot.json`: source/config/test/data hashes at start of this verification.

The original `research/reviews/2026-09-28/readiness_checks.xml` has intentionally been preserved, not overwritten with the new result.
