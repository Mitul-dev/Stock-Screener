# Independent V1 readiness review — 2026-09-28

## Decision

**The existing implementation is a useful V1 prototype, but the real NSE historical-data pilot has not been validated. Do not scale to the full NSE universe or treat the saved pilot results as research evidence yet.**

The next phase remains real NSE EOD data → 20–30-stock pilot → data validation → full V1 pipeline → paper research. No V2, ML, new setup families, or strategy tuning is needed. Repair the integration and evidence gates in the existing design.

This review independently inspected the files and executed checks. It does not adopt the completion claims in `BUILD_STATUS.md`, `V1_COMPLETION_REPORT.md`, `V1_AUDIT_REPORT.md`, or the two pilot reports. Those historical documents have been preserved for the implementation owner to reconcile.

## Scope and reproducibility

- Project found at `C:\Users\mitul\Downloads\Stock Screener\equity-evidence-engine`.
- Read all four requested top-level documents, every application Python source file, every existing test, all four YAML configurations, all three scripts, `pyproject.toml`, `.env.example`, `.gitignore`, `docs/data.md`, and the pilot reports.
- Inspected raw and processed data, schema, coverage counts, recorded corporate actions, manifest, and saved outcome statistics.
- No Git metadata is present in this project or its parent working tree; `git status` reports that it is not a repository. File hashes identify the inspected snapshot instead of a commit.
- No `AGENTS.md` was found in the inspected workspace/project inventory.
- Existing source, configuration, raw files, processed artifacts, and historical reports were not edited. Added this review and files under `research/reviews/2026-09-28/` only. Running tests may create normal Python cache files and temporary test data.
- No real Telegram messages were sent. Telegram credentials were cleared in the test process. No strategy parameters were changed.

Review artifacts:

- `research/reviews/2026-09-28/repository_inventory.txt`: application files and directories; virtual-environment internals and caches excluded.
- `research/reviews/2026-09-28/evidence.json`: independently computed counts/statistics and SHA-256 hashes of inspected application, report, and data files.
- `research/reviews/2026-09-28/test_v1_readiness.py`: isolated acceptance checks asserting the intended behavior.
- `research/reviews/2026-09-28/readiness_checks.xml`: machine-readable results of those checks.
- `research/reviews/2026-09-28/capture_evidence.py`: reproduces artifact statistics and instruments the existing E2E test without modifying it.

## Tests actually run

Using the existing `.venv` (Python 3.11.9):

```powershell
# From the project root; these environment changes apply to this process only.
$env:TELEGRAM_BOT_TOKEN = ''
$env:TELEGRAM_CHAT_ID = ''
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
```

**26 passed, 1 warning, 5.48 seconds.** The warning concerns deprecated Polars String-to-Date casting in `csv_provider.py:15`.

Then:

```powershell
.\.venv\Scripts\python.exe -m pytest research/reviews/2026-09-28/test_v1_readiness.py -p no:cacheprovider --junitxml=research/reviews/2026-09-28/readiness_checks.xml
.\.venv\Scripts\python.exe research/reviews/2026-09-28/capture_evidence.py
```

**11 failed, 2 passed, 0.96 seconds.** These additional checks live outside the default `tests/` collection. Their failures reproduce missing requirements; they are not fixes and are not marked as expected failures. The multi-instrument validation check identifies an API limitation: the current pilot works around it by validating one symbol at a time.

| Additional acceptance check | Result |
| --- | --- |
| Reject null open | FAIL: accepted |
| Reject infinite volume | FAIL: accepted |
| Reject zero close | FAIL: accepted |
| Validate different instruments on the same date without false duplicates | FAIL: dates treated as globally unique |
| Preserve delivery values when provided | FAIL: `ColumnNotFoundError` |
| Exclude a stock with no bars in the latest 60 market sessions | FAIL: still tier 1 |
| Use actual reported turnover for liquidity classification | FAIL: replaced with close × volume |
| Keep incomplete WATCH observations open/censored | FAIL: prematurely EXPIRED |
| Calculate stop from ATR at confirmation | FAIL: detection ATR used |
| Treat one profitable observation as insufficient evidence | FAIL: VALIDATED |
| Use adjusted prices in the existing adjustment-to-feature composition | FAIL: artificial split true range of 50 |
| Next-session entry and executable gap-through-stop loss | PASS: entry 102, stop 98, gap exit 90, gross −3R |
| Strict close above breakout level | PASS: equality does not confirm |

## Critical findings, in repair order

### 1. The pilot input is Yahoo-derived data with fabricated exchange fields

**Evidence:** `scripts/fetch_pilot_data.py:26,34,45–66` calls `yfinance`, describes the NSE format as a simulation, constructs `ISIN = "INE" + symbol + "01010"`, hardcodes `FinInstrmId=123456` and trade count 1000, sets previous close to the current close, and estimates turnover from volume × close. `Src` is nevertheless set to NSE. The raw artifact matches the fabricated ISIN formula in all 32,880 rows; 29,592 rows even fail a basic ISIN format check. A string that passes the format check is not thereby a verified identifier.

**Impact:** This is a provider-derived engineering dataset, not a verified official NSE bhavcopy pilot. The security-master and exchange-turnover requirements have not been exercised. The files do not establish Yahoo price adjustment semantics merely by using `auto_adjust=False`; that assumption must be verified against source documentation and actual corporate-action dates before any additional adjustment.

**Repair:** Preserve these files and explicitly label their origin/limitations. Import genuine exchange files separately, retaining original bytes, authentic identifiers, actual turnover, source dates and URLs. Do not replace fake identifiers with a current ticker mapping retroactively. Verify historical identifier changes with dated evidence.

### 2. Validation does not prevent invalid research

**Evidence:** `ingestion/nse_importer.py:55` writes Parquet before calling any validator. `scripts/run_pilot_pipeline.py:29` catches a validation error, prints it, and continues. `ingestion/validator.py` omits null/nonfinite checks, zero-price rejection, and instrument-aware duplicate keys. It does not check trading-calendar coverage, jumps, staleness, corporate-action continuity, or identity changes.

**Impact:** A successful run or a processed manifest status is not a data-quality pass. Missing mandatory values can flow into features and outcomes.

**Repair:** Validate before publishing processed output; abort research on hard failures. Quarantine invalid inputs with error details. Keep genuine optional delivery values null. Check duplicates by the canonical instrument/session key, with series/exchange ambiguity explicitly resolved. Compare sessions with a sourced exchange calendar, not just equal per-symbol row counts. Flag jumps for investigation rather than deleting them silently.

### 3. Corporate-action adjustment is calculated but not consumed

**Evidence:** `CorporateActionAdjustor` preserves raw OHLCV and adds `adj_*` columns. The pilot passes this frame directly into `FeatureCalculator` at `scripts/run_pilot_pipeline.py:62`; the calculator uses the raw `open/high/low/close/volume` columns. Outcomes receive the same raw feature frame. The acceptance test supplies a flat 2:1 split: adjusted closes are correctly all 50, but feature true range is 50 on the split date.

**Impact:** Calling the adjustor does not establish a corporate-action-safe pipeline. With true unadjusted NSE history, splits can create false volatility and distort setup levels/outcomes. Yahoo-derived input might already have some adjustments; this review does not assume or certify that basis.

**Repair:** Define and test the price basis at each boundary. Feed an explicit adjusted OHLCV projection to features, while retaining raw prices and factors separately. Ensure event levels and executable outcome prices use a consistent basis, including splits during WATCH and holding periods. Define as-of action availability and ex-date handling; a full-history backward adjustment alone does not prove point-in-time safety. Do not add a second adjustment to already-adjusted provider prices.

### 4. Universe and regime do not participate in the pilot research

**Evidence:** `scripts/run_pilot_pipeline.py:71` zeroes the liquidity thresholds. Lines 76 and 81 compute one last-date universe and one full-history regime; neither result is used in event selection or attached to outcomes. Regime configuration disables the NIFTY requirement. No YAML configuration is loaded. The security master is also bypassed; detectors use the symbol as instrument ID despite the fabricated ID column.

`universe/builder.py:17` does filter future rows, which is useful, but lines 23–34 aggregate all past history rather than the last 60 sessions. Coverage can exceed 1. The builder overwrites supplied turnover with close × volume and uses `.last()` without sorting the input. A stock last seen 60 sessions ago remains eligible in the review example.

**Repair:** Use dated security-master resolution and the existing YAML parameters. Build eligibility for each event date using the correct trailing exchange-session window and source turnover; exclude stale/missing bars under an explicit policy. Compute regime from data available through the event date and persist it as context. Whether regime filters events must be specified in the frozen methodology, not decided from performance. Missing breadth/VIX must be disclosed instead of silently interpreted as observed values (the classifier currently supplies defaults).

### 5. Outcome semantics are incomplete

**Evidence:** `outcomes/engine.py:59` expires a WATCH even when fewer than the configured five sessions are available. Line 73 uses ATR from detection rather than confirmation. No +1R/+2R target-touch labels are produced. The code updates MFE/MAE using the entire exit day's range before checking the stop; intraday ordering cannot be inferred from daily OHLC alone. `SetupEvent.transition()` permits every transition without validation, and repeated daily detections are not managed as one active setup lifecycle.

**Repair:** Keep right-censored WATCH/holding events distinct from completed/expired observations; record confirmation ATR and entry date. Add the specified target-touch labels with a documented conservative same-bar stop/target convention. Define whether MFE/MAE are trade-lifetime values or daily-bar bounds. Implement the required transition and repeated-event policy without changing setup thresholds.

Working behavior worth preserving: strict close-above confirmation, next available session open entry, nonpositive-risk invalidation, executable gap-stop losses, and separate gross/net R columns.

### 6. Statistical output can manufacture confidence

**Evidence:** `backtest/controls.py:28` uses unseeded independent-event resampling. Line 43 calls raw event count `effective_n`; distinct detection dates are labeled time blocks. There is no minimum sample or diversity gate. A single +1R observation is returned as `VALIDATED`. The pilot pools both setup families, uses only a zero-R static hurdle, and never invokes the chronological splitting helper. It creates no frozen evidence snapshot or trial registry.

**Impact:** A positive interval relative to zero does not establish validated out-of-sample evidence. Counts of detection dates do not address overlapping 20-session holding periods or correlated stocks. The saved pilot uses the whole available history, so that history should be treated as already explored, not relabeled untouched holdout.

**Repair:** Report event count, unique instruments, actual block definition, and dependence limitations honestly; effective sample size is unknown unless estimated appropriately. Seed and record resampling. Gate validation on a frozen methodology and adequate independent evidence, not just a sign test. Report each setup separately. Keep `baseline_type=STATIC` and describe zero R as a hurdle, not a matched/control strategy. Define chronological split boundaries and purge/censor crossing outcome windows. Save versioned trials, input/config hashes, statistics and outcome snapshots. Do not choose thresholds using these results.

### 7. Ingestion provenance and real-format support remain incomplete

**Evidence:** The importer reads a plain CSV and has no explicit ZIP handling. The optional delivery branches refer to columns already dropped by `select`, causing the reproduced crash. Legacy parsing omits the optional null columns. Canonical rows lack `source_file` and `source_date`. `_update_manifest()` uses today's date for `market_date` and import time for `downloaded_at`, without knowledge of the actual download. The stored manifest has three duplicate entries for the same hash, all with market date 2026-09-28, while data spans 2018–2024. Fetch scripts overwrite raw files on rerun.

**Repair:** Extend the existing importer to parse verified official schemas and ZIP members, with typed normalization, genuine row/source dates, idempotency, immutable input storage and failure records. Record actual download time at acquisition; otherwise leave it unknown and record `imported_at` separately. A file containing many market dates needs a date range or per-date inventory, not today's date. Test known valid official fixtures and malformed/HTML/duplicate/date-mismatch inputs before declaring support.

NSE's current reports page lists CM-UDiFF Common Bhavcopy Final ZIP, security-wise delivery reports, and security files. It states the old CM CSV reports were discontinued from July 8, 2024. See [NSE reports](https://www.nseindia.com/all-reports) and [official UDiFF formats/sample files](https://www.nseindia.com/static/resources/forms-formats-members). The official sample link is `https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Bhavcopy.zip`. A direct read attempt timed out after 30 seconds in this environment. **No official sample was parsed in this review; exact field compatibility remains unverified.** Do not assume the synthetic header `TtlTrfVal` proves current exchange compatibility.

### 8. Costs, product, and reproducibility claims exceed integration

- `config/costs.yaml` uses the key `costs`; `OutcomeEngine` expects `transaction_costs`. The pilot loads neither and uses defaults. GST is not applied. A simple cost approximation is allowed, but it must reflect the declared/configured model and its charge bases.
- `dashboard/app.py:26–28` displays hardcoded UPTREND, 5 setups and VALID data quality. Other pages are placeholders. The dashboard import test verifies importability only. No persisted forward-testing ledger is implemented.
- Snapshot persistence exists as a component but is not wired into pilot research or alerts. Alert IDs are caller-supplied while setup IDs use random UUIDs; repeatable event identity is not guaranteed across reruns. SQLite duplicate suppression works for a repeated identical supplied ID, but this is not end-to-end exactly-once delivery.
- The Telegram test only avoids the network when credentials are absent. Set credentials to empty or mock the request explicitly in tests.
- `yfinance` is used by the fetch scripts but is absent from declared dependencies. Storage calls `to_arrow()` yet PyArrow is not a direct declared dependency. Dependencies are unpinned. A passing existing environment is not proof of a reproducible clean installation.
- `BREAKOUT_V1` reads `lookback_days` but always uses the fixed 252-day feature. VCB's relative-volume threshold is hardcoded. Do not present these as fully configurable without implementation/tests.

## Saved pilot report reconciliation

These are descriptive recalculations of existing files, **not validated strategy findings**:

| Item | Saved report claim | Independently read artifact |
| --- | --- | --- |
| Securities / rows / distinct dates | 20 / 32,880 / 1,644 | Matches |
| Actual data end | 2024-09-01 | 2024-08-30; requested end and actual last bar differ |
| Duplicate symbol/date rows | 0 | 0 |
| Missing exchange sessions | 0 | Not verified against an independent session calendar |
| Total events | 1,121 | 1,121 |
| Completed | 980 | 980 |
| Expired | 141 | 120 |
| Other final states | Not reconciled | 11 CONFIRMED, 10 INVALIDATED |
| Gross mean R | About −0.15 | +0.0701472821 |
| Net mean R | −0.199 | −0.1993184363 |
| Median net R | About −0.21 | −1.1529350695 |
| Effective N | 980 | 980 completed event rows; effective independent N not established |
| Time blocks | 571 | 571 unique detection dates, not validated independent blocks |

The code does not generate the two Markdown pilot reports, so their numbers and conclusions are not mechanically tied to the saved run. Their claims of flawless execution, raw-price verification, mathematical soundness, and readiness for thousands of tickers are unsupported.

## Why the original tests passed

- `tests/leakage/test_leakage.py:34` is a bare `pass` for adjustment leakage.
- `tests/leakage/test_ca.py` prints output but contains no assertions. The separate unit corporate-action test does assert the simple split arithmetic and passes.
- The deep truncation test compares 200-day SMA at day 50, where both values are null. The simpler leakage test similarly compares an uninitialized 252-day high. This does not test those indicators after warm-up.
- Instrumenting `tests/e2e/test_synthetic_e2e.py` produced **48 EXPIRED events, zero completed outcomes**. Its `if outcomes:` at line 79 skips the only statistics assertion. It does not actually test ingestion, VCB, the security master, chronological partitions, snapshots or alerts end to end.
- Integration and property directories contain only initializer files. Dashboard coverage only imports the module; the environment test only asserts true. No existing test exercises `NSEImporter`.

## Requirements versus actual state

| V1 area | Actual state |
| --- | --- |
| Local Python/Polars/DuckDB architecture; no ML | Present; preserve |
| CSV ingestion and basic storage | Present; real NSE parser/provenance unverified |
| Authentic security identity/history | Component exists; pilot bypasses it and fabricates IDs |
| Corporate actions | Simple split arithmetic works; price-basis integration not validated |
| Point-in-time universe | Future-row filter exists; trailing window and pilot integration defective |
| Features and exactly two setup families | Present; adjusted-input and configuration gaps |
| Regime context | Classifier exists; historical event integration absent |
| Outcomes | Entry/stop/cost skeleton present; censoring, ATR timing, target labels incomplete |
| Static baseline and uncertainty | Present; validation status and sample/dependence treatment unsafe |
| Discovery/validation/holdout | Helper exists; pilot does not use it or embargo crossing outcomes |
| Trial registry / immutable runs | Not implemented in pilot |
| Evidence snapshots | Component exists; pilot/alert linkage absent |
| Telegram | Basic send and duplicate-ID tracking; no complete evidence-driven alert flow |
| Dashboard / forward ledger | UI scaffold; hardcoded overview and no real forward ledger |
| 20-stock engineering data | Present, Yahoo-derived with mock exchange fields |
| Genuine NSE data pilot / paper research readiness | Not demonstrated |

## Implementation brief for Antigravity

Proceed within the existing architecture, in this order:

1. **Contain misleading outputs.** Mark old pilot data/reports as exploratory provider-derived artifacts and current readiness as blocked by the findings above. Keep old files recoverable. Replace hardcoded dashboard status with unknown/no validated run until real inputs exist.
2. **Repair the ingestion boundary.** Obtain a genuine official bhavcopy sample and format documentation, plus source security identity, session/calendar and corporate-action evidence. Add ZIP/plain CSV handling to the existing importer, provenance and immutable manifests, null/finite/schema/identity validation, and fail-closed orchestration. Implement missing delivery as null; verify delivery joins before using them.
3. **Pass a small data acceptance run before expanding history.** Reuse a fixed 20–30-stock pilot list without selecting it for returns. Check at least one verified split/bonus boundary and an identifier-change case where sourced history is available. Report current-liquid-stock selection/survivorship limitations explicitly. Then extend to several years without redefining the cohort based on results.
4. **Wire the existing V1 components.** Resolve stable instrument IDs, use the documented adjusted/raw bases correctly, apply daily eligibility and record point-in-time regime, load frozen YAML configuration, fix censoring and confirmation ATR, label targets, and preserve deterministic event/run identities.
5. **Make research outputs reproducible.** Register hypothesis, setup/universe/methodology versions, costs, baseline and split dates before evaluation. Treat already inspected history as explored. Add split-boundary purge/censor handling and sample/dependence safeguards. Generate both requested reports directly from run artifacts; persist evidence snapshots with hashes and seeds.
6. **Rerun all tests and non-vacuous acceptance checks.** Require known confirmed and completed events, both setup families, all pipeline stages, split continuity and mature-window truncation equivalence. Adapt the isolated composition test to the repaired caller boundary if adjustment projection lives there. Verify the underlying invariant, not one mandated implementation.
7. **Begin paper research only after these gates pass.** Persist every forward event, including invalidated/censored cases, and read frozen evidence in the dashboard/alerts. Keep full-universe expansion and V2 out of this repair phase.

The independent review is complete. The repairs, authentic-data acquisition and full V1 pilot are outstanding implementation work; none is claimed complete by this report.
