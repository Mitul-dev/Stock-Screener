# PROJECT HANDOFF - INDIAN EQUITY EVIDENCE ENGINE

Updated: **2026-10-21 (Asia/Calcutta)**.
Recipient: **Desktop Astra**, continuing the Stock Screener Engine project.
Repository filename: **`hanout.md`** (the existing historical spelling).

## Start here: use the continuation branch

The repository is the source of truth. Inspect current code, configuration,
actual test collection, branch state and changes after the baselines below.
Preserve working components and earlier evidence.

- Repository: https://github.com/Mitul-dev/Stock-Screener
- **Continuation branch: `codex/historical-source-inventory`**
- The latest source-preparation baseline before this handoff-only commit is
  **`045c0ce4dab613f3648775457799a48f7aefaf66`**.
- The latest executed software-verification baseline is
  **`02915d7c1e292c2405f403810ecb369ad2f0e021`**.
- This updated handoff is a subsequent documentation-only commit on the
  continuation branch. Use its current HEAD; inspect any later changes.
- The project is at the repository root. There is no nested
  `equity-evidence-engine/` checkout directory.

At this transfer, the PR stack is:

| PR/ref | Branch relationship | State at transfer | Baseline |
|---|---|---|---|
| [PR #1](https://github.com/Mitul-dev/Stock-Screener/pull/1) | `codex/run-quality-evidence-consumers` -> `main` | Open draft; unmerged | `02915d7c1e292c2405f403810ecb369ad2f0e021` |
| [PR #2](https://github.com/Mitul-dev/Stock-Screener/pull/2) | `codex/historical-source-inventory` -> `codex/run-quality-evidence-consumers` | Open draft; unmerged | `045c0ce4dab613f3648775457799a48f7aefaf66`, then this handoff commit |
| `main` | Original implementation plus original handoff | Does not yet contain either draft milestone | `ef91f777104ee647f25ed72b66fdfb8650142db4` |

**The continuation branch includes both milestones. A checkout of main alone
does not.** Recheck remote PR/ref state on arrival; it may change after transfer.
No PR was merged as part of this handoff.

**Current decision: NOT READY FOR REAL-DATA PILOT.**
**Paper research: NOT APPROVED.**

The current-run quality/dashboard/dry-run alert milestone is implemented and was
tested. Historical source preparation is saved, but genuine multi-year acquisition,
calendar/action/identity reconciliation and a historical pilot are incomplete.

**Next assignment: resume actual historical source acquisition and reconciliation
on the fixed cohort, after verifying the Desktop execution environment and
rerunning the software baseline.** The old assignment to build the current-run
consumers is completed on PR #1; inspect and preserve that work.

## Execution context and what was blocked

The first Work session had a usable Linux/Python workspace and executed tests.
Before the next source-preparation step, that execution workspace became
unavailable. GitHub and an in-memory JavaScript code runtime remained usable.

During source preparation:

- Existing original fixture bytes were read from GitHub, verified and parsed in
  memory; the cohort and source inventory were committed.
- Official web page/PDF text and CSV download links were researched.
- **No new historical NSE archive/date was acquired to disk.**
- **Python tests, calendar derivation, multi-year ingestion and a historical
  production run were not executed.**
- No real Telegram messages were sent.

This limitation belonged to the prior Work execution environment. It is not a
claim that Desktop Astra lacks Python, terminal access, downloads or network
access. Inspect the actual Desktop environment and use available execution
capabilities. If execution works, proceed with real retained-byte acquisition and
validation; source planning alone does not finish the next milestone.

If access is read-only or execution remains unavailable, report the exact
limitation and deliver concrete findings/patches without claiming downloads or
tests occurred. Previous XML is historical evidence, never a substitute for
executing checks on the current checkout.

## Purpose and fixed boundaries

This is a personal-use Indian cash-equity EOD research and alerting engine:
when a precisely defined technical setup appeared, what happened afterward
under recorded outcome and cost assumptions?

The intended progression remains genuine historical NSE data -> fixed cohort
engineering pilot -> validation and reproducible evidence -> separate
paper-research admission decision.

User constraints carried forward:

- Stay within V1. No ML, new strategies, intraday, F&O or BSE expansion.
- Preserve BREAKOUT_V1 and VCB_V1 thresholds and the existing YAML configuration.
  Current setup versions are BREAKOUT_V1.0 and VCB_V1.0.
- Do not optimize parameters, substitute cohort members or tune against holdout
  because signals are rare or outcomes are attractive/disappointing.
- Preserve original source bytes, changed input versions and earlier experiments.
- Keep raw OHLCV, source identity, adjustment factors and adjusted research
  prices distinguishable.
- Never invent identifiers, identifier history, turnover or delivery values.
  Missing delivery remains null. A static hurdle remains labelled STATIC.
- Software checks and engineering quality permission do not validate a strategy.
  Zero setups, losses and INSUFFICIENT EVIDENCE are legitimate outcomes.
- Use local dry-run alerts or mocked delivery. Real Telegram delivery still
  requires explicit authorization, which has not been given.
- This handoff does not approve paper research.

## Read in this order

1. This file, `BUILD_STATUS.md`, and the actual PR/ref state.
2. `research/reports/historical_source_preparation_2026-10-20.md`.
3. `research/pilot/README.md`, `cohort_v1.json`,
   `historical_inventory_v1.json`, `source_catalog_2026-10-20.json` and
   `verification_2026-10-20.json` in `research/pilot/`.
4. `docs/historical_sources.md`.
5. `research/reports/run_consumers_integration_2026-10-20.md`,
   `run_consumers_verification_2026-10-20.json`, and the actual consumer code/tests.
6. `README.md`, `docs/data.md`, `docs/pilot_pipeline.md`.
7. Earlier `production_pipeline_integration_2026-10-20.md` and
   `official_fixture_ingestion_2026-10-20.md` under `research/reports/`, then
   relevant actual source/configuration/tests.

Older `V1_COMPLETION_REPORT.md`, `V1_AUDIT_REPORT.md`,
`V1_REPAIR_REPORT.md` and September review material are preserved history.
Some readiness claims were disproved by independent execution; some described
defects were later repaired. They are not current admission decisions.
The older production/ingestion reports' remaining-work lists predate the consumer
milestone. The historical-source report's next task is current.

## Repository map

| Area | Paths |
|---|---|
| Source preparation | `research/pilot/`, `docs/historical_sources.md` |
| Official acquisition/import | `scripts/fetch_official_nse_fixture.py`, `scripts/import_nse_eod.py` |
| Ingestion/engineering quality | `src/equity_engine/ingestion/nse_importer.py`, `validator.py`, `quality.py` |
| Production orchestration | `scripts/run_pilot_pipeline.py` |
| Corporate actions | `src/equity_engine/corporate_actions/adjustor.py` |
| Features/universe/regime | `src/equity_engine/features/calculator.py`, `universe/builder.py`, `regime/classifier.py` |
| Setups | `src/equity_engine/setups/breakout.py`, `vcb.py` |
| Outcomes/research | `src/equity_engine/outcomes/engine.py`, `backtest/engine.py`, `backtest/controls.py` |
| Frozen evidence/current-run verification | `src/equity_engine/evidence/snapshot.py`, `evidence/run.py` |
| Dashboard/alerts | `src/equity_engine/dashboard/app.py`, `alerts/telegram.py`, `scripts/preview_run_alerts.py` |
| Identity helper | `src/equity_engine/security_master/master.py` |
| Configuration | `config/setups.yaml`, `universe.yaml`, `costs.yaml`, `regime.yaml` |
| Tests | `tests/unit/`, `tests/integration/`, `tests/leakage/`, `tests/e2e/` |

Python 3.11+ and the existing Polars, NumPy, DuckDB, YAML, Streamlit and requests
stack are declared in `pyproject.toml`. Dependencies are not lockfile-pinned.
Reuse working infrastructure/components.

## Implemented before and during PR #1

### Original official NSE fixture and repeatable ingestion

Unchanged retained source:
`tests/fixtures/nse/BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv.zip`.

- Market date: 2026-10-08. Original acquisition: 2026-10-20.
- Official listing: https://www.nseindia.com/all-reports
- Acquisition URL: https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv.zip
- ZIP size: 208,947 bytes.
- ZIP SHA-256:
  `07fdfc3409b83fac6ee4a736ceb4fde20069c5d1a490d960b332c178cb703e39`.
- One CSV member; 3,733 rows, including 2,681 EQ rows.
- CSV-member SHA-256:
  `3bfb33cd4a0eb55b77ed2b24fd95cac6803edf00256bee65796ede4ee7549e53`.
- ZIP member CRC-32: `12e2ccf7`.
- Adjacent `.zip.provenance.json` retains the original acquisition time,
  URLs/headers, hashes, columns, counts and reference rows.
- `TtlTrfVal` is actual reported turnover, not close times volume.
- No authentic delivery fields occur in this fixture; normalized delivery is null.

This proves one current daily schema, not multi-year history, authentic legacy
or delivery parsing, identity-history integration or action reconciliation.

The importer validates before publishing, archives exact source bytes by SHA-256,
versions normalized files by input hash/parser revision, and binds outputs to
immutable receipts. Identical replays verify/reuse intact pairs. Changed bytes
produce separate preserved versions. Corrupt/incomplete raw/output/receipt
artifacts, HTML/malformed input, ambiguous multi-CSV ZIPs, invalid OHLCV/required
fields and invalid supplied delivery are rejected. Older manifests are preserved;
locking prevents lost concurrent appends. Unknown acquisition time is not replaced
with import time.

### Configured chronological production execution

The runner preserves raw identifiers, reported turnover, source fields and
raw/adjusted prices through features, events and outcomes. It does not manufacture
ticker-shaped ISINs.

Existing YAML setup/universe/cost/regime settings are loaded. Universe eligibility
uses reported turnover, coverage and raw-price thresholds at each candidate's
detection date; exclusions and reasons remain auditable.

Features group by source instrument identity and preserve historical symbols.
Split/bonus adjustment handles missing ex-date bars, rejects invalid factors and
repeat adjustment, and rejects unsupported/null supplied action types/identities.
Official historical continuity across source ISIN changes remains unresolved.

The actual runner invokes `ResearchEngine.split_data` and separate bounded
backtests for discovery, validation and holdout. Existing 60/20/20 allocation,
five-session watch expiry and 20-session holding timeout remain unchanged.
Small datasets have disjoint/empty later partitions. Incomplete WATCH/CONFIRMED
outcomes are censored and excluded from frozen trade-R evidence. Eligible terminal
COMPLETED/FAILED trades, including losses, remain. Expired/invalidated candidates
remain records without becoming trade-R evidence.

Families and partitions remain separate. Configured costs/GST are applied.
Typed empty outputs and explicit insufficient-evidence snapshots support
zero-event runs. Frozen metadata/outcome hashes and partition/cutoff provenance
are required; snapshot identities cannot be overwritten.

### Persisted quality, verified consumers and portability: completed

`ingestion/quality.py` reuses `DataValidator` and writes 14 engineering checks
with counts, examples, limitations and blocking issues. The report binds to
trial/input/configuration/code hashes and the run fingerprint.

Checks cover OHLCV, source/date identity, requested cohort, concurrent symbol
ambiguity, observed-session gaps, relative staleness, setup lookback depth,
adjusted-return flags, delivery/acquisition availability, optional supplied
calendar, unresolved action/identity reconciliation and index availability.

- Missing delivery, short history and zero setups are not arbitrary failures.
- The versioned absolute adjusted-return review trigger is at least 50%;
  this is a quality diagnostic, not a strategy parameter or a complete anomaly
  detector. A smaller return cannot clear a known unsupported restructuring.
- Supplied calendar discrepancies, invalid source/identity, absent requested
  cohort members, ambiguity and unexplained flagged returns are blocking.
- Failed-quality runs retain diagnostic outcomes but mark evidence ineligible
  with a withholding reason, publish no snapshots and withhold alerts.
- Gaps/staleness and missing optional/source-history information remain visible.
  PASSED_WITH_WARNINGS permits engineering inspection, not pilot admission.

New run manifests are **schema version 2**, with
**`artifact_path_contract: run-relative-v1`**.
`RunEvidence(manifest_path)` checks the manifest hash, required artifact bytes,
quality binding/decision, and frozen identity/setup/version/partition/cutoff and
statistics. Original absolute paths remain historical metadata; verified run-local
references make new bundles portable. These hashes detect changed bytes, not a
trusted author or authenticated external raw source.

The dashboard now selects a current run and displays its actual quality, sources,
partitions, cutoffs and evidence. It no longer derives validation from a nonempty
legacy outcome file. Missing quality is UNAVAILABLE; failed/corrupt evidence
cannot yield an honest validated status. Legacy schema-1 runs are preserved and
require regeneration for the current quality/consumer contract.

`TelegramAlerter.send_alert` requires a manifest and recorded event/instrument/
setup/version/EOD date. An explicit snapshot must match; otherwise it selects the
latest matching frozen evidence with cutoff **strictly before** the event date.
Event and snapshot IDs are different. A partition-end snapshot cannot justify its
own earlier event. Delivery defaults to `dry_run=True`, including with populated
credentials. Dry-run and sent identities are separate. Repeats reverify evidence,
and existing outbox rows survive migration. `TEST_ENV` does not bypass the run
contract. `last_error` records rejection reasons.

Conceptual call:

```python
alerter.send_alert(
    event_id, instrument_id, setup_version, message,
    snapshot_id=None, manifest_path=manifest_path,
    event_time=source_eod_date, dry_run=True,
)
```

`scripts/preview_run_alerts.py` wires real run candidates to this local-only
consumer. The separate explicit send path was mocked in tests, never exercised
against real Telegram delivery.

The CSV provider's removed string-to-date cast was replaced by explicit ISO
`str.to_date` parsing, fixing the observed Polars 2.0 compatibility failure.
All four original YAML files and original official fixture/provenance bytes were
unchanged by these milestones.

## Last actual Python verification: scope and reproduction

| Stage | What happened |
|---|---|
| Original pre-handoff implementation | Historical Windows report: 135 passed, one old date-cast warning. |
| Fresh baseline before PR #1 edits | Linux/Python 3.12.14 with Polars 2.0: 135 collected, 134 passed, one CSV-provider failure; one SQLite adapter warning. |
| PR #1 final consumer subset | 55 collected, 55 passed; no warnings. |
| PR #1 final full selection | **189 collected, 189 passed; no warnings.** |
| PR #2 source preparation | No Python execution. In-memory source-byte/row and inventory checks only. |
| This 2026-10-21 handoff update | Documentation only; no new Python/test/download execution. |

The 189-case result belongs to the software at
`02915d7c1e292c2405f403810ecb369ad2f0e021`. PR #2 added source-preparation
JSON/docs without runtime/configuration changes. Do not present that previous
189-case run as newly executed on Desktop. Rerun and report the actual result.

Execution evidence:

- `research/reports/run_consumers_baseline_tests_2026-10-20.xml`
- `research/reports/run_consumers_tests_2026-10-20.xml`
- `research/reports/run_consumers_full_tests_2026-10-20.xml`
- `research/reports/run_consumers_integration_2026-10-20.md`
- `research/reports/run_consumers_verification_2026-10-20.json`

Last environment: Python 3.12.14, Polars 2.0.0, NumPy 2.3.5, pandas 2.2.3,
DuckDB 1.5.6, PyYAML 6.0.3, Streamlit 1.66.0, requests 2.34.2, pytest 9.1.1,
Hypothesis 6.170.5. Installation on Desktop may resolve different versions.

For a new Windows/PowerShell checkout:

```powershell
git clone --branch codex/historical-source-inventory https://github.com/Mitul-dev/Stock-Screener.git
cd Stock-Screener
git status --short --branch
git log -5 --oneline
git rev-parse HEAD
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[test]"
$env:TELEGRAM_BOT_TOKEN = ""
$env:TELEGRAM_CHAT_ID = ""
.venv\Scripts\python.exe -m pytest tests research/reviews/2026-09-28/test_v1_readiness.py -p no:cacheprovider -q --junitxml=research/reports/desktop_baseline_tests_2026-10-21.xml
```

For an existing checkout, inspect/preserve local changes and fetch the correct
remote branch before switching/updating. Do not reset user work.
On Linux/macOS use `.venv/bin/python` and equivalent environment-variable syntax.

Tests use retained fixtures and temporary data; no live NSE download or Telegram
delivery is needed for the offline suite. Use a new XML name for a later execution
rather than overwriting previous evidence.

The consumer suite is `tests/integration/test_run_consumers.py` (54 new integration
cases) plus the updated Telegram unit case. It exercises actual Streamlit views
and real production/frozen files, absent/failed quality, missing/corrupt artifacts,
wrong setup/version/identity/date, future evidence, eligibility, moved runs,
outbox migration and repeat-alert verification.

Default pytest collection is only `tests/`; the full command above additionally
includes the original 13 readiness cases. The separate historical September
17-case review suite was not rerun/updated in these milestones. At least one
older leakage test has a `pass` body. Green tests are not proof of every gate.
Count collected parameterized cases, not test function declarations.

## Preserved run evidence and usable inspection commands

The latest portable, quality-bearing examples are committed under
`research/reports/run_consumers_acceptance_2026-10-20/`:

| Run | Rows / source IDs | Candidates | Evaluated / eligible outcomes | Snapshots | Prepared local previews |
|---|---:|---:|---:|---:|---:|
| `synthetic/` | 5,980 / 5 | 11 | 8 / 6 | 6 | 4 |
| `official_single_day/` | 20 / 20 | 0 | 0 / 0 | 2 | 0 |

The synthetic run has 1,200 supplied sessions, separate family/partition evidence
and two censored discovery outcomes. Its seven rejected previews include
discovery candidates without earlier frozen evidence and universe-ineligible
candidates. It is engineering evidence, never an official strategy sample.
Synthetic status is EXPERIMENTAL. The official one-session run is INSUFFICIENT
EVIDENCE, with no validation/holdout sessions. Both quality reports are
PASSED_WITH_WARNINGS, with unresolved source/history limits.

The earlier `research/reports/production_acceptance_2026-10-20/` bundle and
earlier reports remain preserved. Some older local runs in ignored `data/`
directories are not available in a clean clone. The latest two examples above
are committed and portable; do not describe them as missing from a clone.

After environment setup, inspect the current examples:

```powershell
.venv\Scripts\python.exe -m streamlit run src/equity_engine/dashboard/app.py
.venv\Scripts\python.exe scripts/preview_run_alerts.py research/reports/run_consumers_acceptance_2026-10-20/synthetic/manifest.json --outbox data/processed/desktop_preview.sqlite
```

Select `research/reports/run_consumers_acceptance_2026-10-20` as the dashboard's
runs folder. The preview command never sends externally.

New production runs retain `features.parquet`, `universe.parquet`,
`events.parquet`, `outcomes.parquet`, `regime.parquet`, `statistics.json`,
`quality.json`, frozen snapshot metadata/outcomes, `manifest.json` and
`manifest.sha256`. Manifests retain trial identity, input/config/code hashes,
resolved configuration/costs, seed, boundaries and methodology/setup versions.
Stable fingerprints do not replace unique execution/run IDs or a global
paper-research hypothesis registry.

## Historical source preparation: saved in PR #2, not an acquired history

The fixed cohort is `research/pilot/cohort_v1.json`, ID
`NSE_FIXED_ENGINEERING_20_V1`:

```text
RELIANCE TCS HDFCBANK INFY ICICIBANK HINDUNILVR ITC SBIN BHARTIARTL KOTAKBANK
LT ASIANPAINT AXISBANK MARUTI SUNPHARMA TITAN BAJFINANCE TATASTEEL ULTRACEMCO WIPRO
```

Each member's observed ISIN, source security ID and company name was extracted
from the original 2026-10-08 EQ source row, not filled from memory. Historical
`valid_from`/`valid_to` remain null and continuity is UNVERIFIED. This is a
current-survivor engineering cohort, not a historical membership universe,
matched-control sample or survivorship-safe research sample.

`research/pilot/historical_inventory_v1.json` records:

- Proposed source window: **2023-01-01 through 2026-10-08**. This is a planning
  target chosen before new outcomes, not a completed or admitted evaluation span.
- Seven source families; 12 checkpoint requests, of which only the 2026-10-08
  anchor is retained. The other requests are unfetched and their session/archive
  availability is not verified.
- A full 20-member action/identity review queue and positive restructuring cases.
- **One retained official session. Zero new historical market dates acquired.**
- Expected/missing session counts and historical partition boundaries remain null.
  No authority `calendar.csv` or approved engine-ready action feed was produced.

The 14-source catalogue, `source_catalog_2026-10-20.json`, distinguishes official
page/PDF text read, resolved but unread CSV links, and original bytes actually
retained. Web lookup text is not a saved original PDF/CSV acquisition receipt;
do not invent hashes for those documents.

`verification_2026-10-20.json` and the source-preparation report record the
in-memory JavaScript checks: original ZIP/member hashes and CRC, all original
columns/3,733 rows, all 2,681 EQ rows' date/source/identity/duplicate/numeric OHLCV
and reported turnover checks, exact 20-member equality to the previous smoke
cohort, null historical validity, inventory/source-reference checks, and saved
artifact hashes. These were **not Python pipeline or regression tests**.
The Python reproduction snippet in the report was provided, not executed then.

**The new source-inventory JSON is planning data. The production runner does not
load it or automatically enforce all its unresolved admission gates.**

### Source and methodology blockers that must be resolved

| Gate | Current fact / required next work |
|---|---|
| Historical schema boundary | NSE's report listing says legacy CM Bhavcopy/Common Bhavcopy were discontinued from 2024-07-08. Existing official acquisition command validates UDiFF only. Acquire a genuine legacy checkpoint and independently reconcile header, dates, identifiers, OHLCV and turnover/units. |
| Authority calendar | Retain each year's CM trading-closure notices and subsequent amendments; reconcile special live/Muhurat sessions. Verified document examples include Saturday 2024-03-02 and 2024-05-18. Weekdays, downloaded bars and clearing holidays are not an authority trading calendar. |
| RELIANCE 2023 restructuring | Official source identifies the 2023-07-20 financial-services demerger. Existing split/bonus handling does not reconcile it. No factor is approved. |
| ITC 2025 restructuring | Scheme effective date and record date are different fields; confirm CM ex-date from retained notice. Hotels demerger remains unsupported/unreconciled. No factor is approved. |
| Documented split/bonus examples | RELIANCE 2024-10-28 has candidate factor 2; BAJFINANCE 2025-06-16 components 2 and 5 give candidate combined factor 10. These are unapproved until CM identity/notice/raw-bar reconciliation. Apply components once, not a combined factor twice. |
| Source identity changes | Current runner groups by raw ISIN. Resolve dated economic continuity while retaining original IDs; do not filter all years by the 2026 ISIN, stitch reused tickers or invent a stable identity. |
| Complete action coverage | Positive cases are discovery examples, not a complete feed or proof that other members are action-free. Review the full interval for all 20 stocks. |
| Delivery/index inputs | Authentic delivery parsing and official index history remain unacquired/unverified. Preserve null delivery and visible UNKNOWN regime; older Yahoo files are not official evidence. |

Official links and exact discovery limits are in `docs/historical_sources.md`
and the source catalogue. Some NSE derivatives-department notices were used only
to cross-check underlying equity actions; no derivatives data/logic/scope was
introduced.

Unsupported restructurings cannot be relabelled SPLIT/BONUS, ignored because
their return is below 50%, or bypassed by silently dropping stocks/dates.
Address affected histories through a documented V1 methodology decision and
appropriate source-backed withholding; preserve raw data and record unresolved
coverage. Do not infer permission to expand strategies.

## Desktop's next concrete sequence

1. **Verify checkout and capabilities.** Fetch the continuation branch, inspect
   repository/AGENTS instructions and working-tree changes, confirm Python and
   network/source access, and inspect changes after the listed commits.
2. **Rerun the actual baseline.** Use the full test selection above with empty
   Telegram credentials; record collection, failures, versions and a new XML.
   Reproduce the cohort/fixture verification with Python using the retained
   original ZIP and the source-preparation report's read-only snippet.
3. **Retain authority source bytes.** Acquire original annual CM calendar notices
   for 2023-2026, amendments/special-session notices, relevant CM action and dated
   identity notices. Preserve filenames/bytes, requested and final URLs, acquisition
   time, status/headers and hashes. Do not convert an access failure into a holiday,
   an absent action or fabricated data.
4. **Acquire/reconcile real checkpoints.** Begin with genuine legacy and UDiFF
   transition samples from the inventory and relevant special-session/action
   surroundings. Verify date/source/schema/identity/turnover independently.
   Do not run pre-transition dates through the UDiFF-only fetcher.
5. **Resolve dated identities and unsupported actions.** Determine the V1 treatment
   of affected histories before treating complete raw downloads as usable adjusted
   research history. Add meaningful source/production tests for actual changes.
   Planning JSON does not itself implement that treatment.
6. **Extend to every reviewed expected session.** Retain originals and versions;
   measure cohort completeness, gaps/suspensions/staleness, action discontinuities,
   source schemas, warmup and actual nonoverlapping evaluation/follow-up coverage.
   Missing delivery stays null; missing index/VIX context remains explicit.
7. **Run a genuine historical engineering pilot only after critical gates pass.**
   Persist run quality, bounded outcomes, snapshots/manifests, actual commands,
   test results and remaining limitations. Preserve zero-event/loss/insufficient
   results. Reassess engineering admission separately from paper research.

An existing UDiFF checkpoint command, once execution is available and its session
has been checked against calendar sources, is:

```powershell
.venv\Scripts\python.exe scripts/fetch_official_nse_fixture.py --market-date 2024-07-08 --destination data/raw/historical_checkpoints/udiff
```

This checkpoint command was **not run** during source preparation or this transfer.
It is not a legacy downloader or a complete historical/calendar acquisition.
Use `docs/historical_sources.md` for the full acquisition/reconciliation contract.

## Remaining statistical and point-in-time limitations

- Current metrics use deterministic row bootstrap and a STATIC hurdle. The old
  pure-OOS/minimum-distinct-date rule can still label a small sufficiently
  positive sample VALIDATED. It is not independently approved adequate-sample or
  dependence-adjusted validation.
- `effective_n` currently means observation count, not a demonstrated
  dependence-adjusted sample size. Overlapping holdings/market clustering remain.
- Quality is assessed over the supplied run, not independently reconstructed
  historical as-of quality. Caller-supplied calendar content is not automatically
  authenticated.
- Adjustment basis cutoff is distinct from evidence/partition cutoff. Later split
  factors rescale earlier adjusted absolute values; raw execution prices remain.
  Strict earlier evidence selection does not resolve broader point-in-time
  corporate-action methodology.
- Universe artifacts describe candidate detection dates, not a full historical
  NSE membership database. Regime breadth describes eligible supplied-cohort
  stocks, not the whole market. Missing index/VIX/breadth is not manufactured.
- Do not claim profitability, calibrated probabilities, matched controls,
  survivorship safety, a production-ready trading tool or approved paper research.

## Portability and evidence preservation

- `data/raw/`, `data/processed/`, virtual environments, credentials, caches and
  runtime locks are ignored. Local desktop data does not appear in another
  account simply because reports mention its absolute paths.
- The original official fixture/provenance, latest portable acceptance bundles,
  source-preparation artifacts and XML/reports are committed.
- Older reports/frozen metadata contain absolute Windows/Linux paths. Current
  schema-2 consumers follow run-local artifact references; older schema-1 bundles
  are retained history. Regenerate a new run where a current contract is required.
- Never rewrite frozen metadata just to fix an old absolute path: that changes
  hashes. Preserve originals, receipts, changed-input versions and earlier runs.
- `.gitattributes` preserves bytes. Avoid blanket line-ending conversion, source
  fixture repacking and mass formatting.
- Atomic publication uses filesystem link/rename behavior. An older restricted
  sandbox denied those operations; that did not justify removing safeguards.
  Use an appropriate supported local filesystem on Desktop.
- `.env.example` has placeholders. Credentials are unnecessary for offline tests
  and local preview. Keep real Telegram environment values empty during verification.

## What to return after continuing

Report concrete behavior/data acquired, files changed, actual commands/test
collection, failures, unexecuted checks, source hashes/provenance and remaining
gates. Link fresh evidence and preserve the distinction among software
integration, original-source coverage, engineering admission and paper research.

The first new result sought is **actual retained historical/calendar/notice
bytes and reconciled checkpoint coverage**, not another declaration that the
already-completed consumer milestone should be started.

Do not repeat old READY claims or count earlier XML as freshly executed tests.
Change admission only after independently verifying the actual critical gates
against the current implementation and genuine sources.
