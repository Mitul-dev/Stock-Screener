# Build Status

Current milestone: HISTORICAL SOURCE PREPARATION; ACQUISITION BLOCKED
Readiness: NOT READY FOR REAL-DATA PILOT
Source-preparation review: 2026-10-20
Last executed Python verification: prior consumer milestone, 2026-10-20
Paper research approval: NOT GRANTED.

## Current historical-source preparation

- The existing 20-stock engineering cohort is now frozen from original retained source rows in `research/pilot/cohort_v1.json`; source ISIN/security IDs are not invented historical validity ranges.
- Original ZIP SHA-256, member SHA-256 and CRC, 3,733 rows, all 2,681 EQ rows and the unchanged 20-member smoke cohort were independently checked in the code runtime.
- A proposed 2023-01-01 through 2026-10-08 source window, official source catalogue, 12 checkpoint requests and action/identity reconciliation queues are recorded.
- Official documents identify a schema transition, special Saturday sessions, and cohort restructurings requiring review beyond the current split/bonus handler.
- Only one official session is retained. Expected/missing session counts and historical partition boundaries remain unknown; no `calendar.csv` or approved action feed is fabricated.
- Execution workspace is unavailable. Historical archive downloads, Python tests and historical production runs were not executed in this step.
- Runtime code, configuration, original fixtures and frozen outputs are unchanged by source preparation. This work depends on still-unmerged draft PR #1.

See `docs/historical_sources.md`,
`research/pilot/historical_inventory_v1.json` and
`research/reports/historical_source_preparation_2026-10-20.md`.

## Previously verified implementation

- Official original NSE CM UDiFF ZIP for 2026-10-08 remains unchanged with its acquisition receipt and source reconciliation tests.
- Source identifiers, reported turnover, raw and adjusted OHLCV, content-addressed archives, safe replay and chronological production partitions remain intact.
- Each new run persists `quality.json`, linked by hash to its manifest and frozen snapshots. Existing market validation is reused.
- Quality records counts and status for OHLCV, source/date identity, requested cohort, ambiguous identities, cohort-relative gaps/staleness, setup lookback depth, abnormal adjusted returns, delivery, acquisition, optional calendar and unresolved source/history gates.
- Missing optional delivery remains null; zero setups and short history do not become arbitrary quality failures.
- Critical quality failures retain diagnostic outcomes but mark all evidence ineligible, publish no snapshots and withhold alerts.
- Version 2 manifests provide run-relative output/snapshot paths. Consumers verify the selected manifest, artifact bytes, quality identity, snapshot identity/setup/version/partition/cutoff, configuration and recorded statistics.
- Dashboard selects a run and displays its quality, sources, partitions, cutoffs and frozen evidence. It no longer reads legacy outcomes or treats nonempty outcomes as validation.
- Alerts require the recorded event, instrument, setup version and EOD date, with matching frozen evidence ending strictly before the event. Default delivery is a local DRY_RUN. Repeats reverify evidence; dry-run and sent identities remain separate.
- Existing outbox rows and older reports/frozen evidence are preserved. Legacy run manifests require regeneration to use current consumers.
- Existing configuration and strategy thresholds remain unchanged. The deprecated CSV date cast was replaced for Polars 2.0 compatibility.

## Prior consumer milestone test execution (not rerun in source preparation)

Environment: Python 3.12.14; Polars 2.0.0; NumPy 2.3.5; DuckDB 1.5.6;
PyYAML 6.0.3; Streamlit 1.66.0; requests 2.34.2; pytest 9.1.1; Hypothesis 6.170.5.

Baseline on `ef91f77`: **135 collected, 134 passed, 1 failed**. Unpinned dependencies
installed Polars 2.0, which rejects the old CSV provider String-to-Date cast.
The baseline failure is retained in `research/reports/run_consumers_baseline_tests_2026-10-20.xml`.

Final command (Telegram environment values empty):

```bash
.venv/bin/python -m pytest tests research/reviews/2026-09-28/test_v1_readiness.py -p no:cacheprovider -q --junitxml=research/reports/run_consumers_full_tests_2026-10-20.xml
```

Result: **189 collected, 189 passed**, no warnings. This includes the 135 baseline
cases plus 54 new integration cases. The consumer subset passed 55 cases, including
the updated Telegram unit case. Actual Streamlit pages, real frozen files, corrupt
and missing artifacts, temporal/identity mismatches, failure withholding, portability,
outbox migration and dry-run idempotency are exercised.
The historical September 17-case review suite was not rerun or modified.

## Retained engineering evidence

`research/reports/run_consumers_acceptance_2026-10-20/` contains freshly generated,
portable synthetic and official single-day runs, including quality reports and
frozen files. The synthetic run has 11 candidates, eight evaluated outcomes,
six eligible outcomes and four prepared local dry-run alerts; seven candidates
are rejected for missing earlier evidence or universe ineligibility. The genuine
one-day run contains 20 source identities, zero events and INSUFFICIENT EVIDENCE.

See `research/reports/run_consumers_verification_2026-10-20.json` and
`research/reports/run_consumers_integration_2026-10-20.md` for details.

## Remaining gates

- Obtain genuine multi-year historical coverage for the fixed 20–30-stock cohort, sufficient warmup, evaluation partitions and follow-up.
- Supply and authenticate the expected NSE session calendar; observed-cohort gap counts cannot reveal whole-cohort missing dates.
- Reconcile authentic corporate actions, source dates/notices, identifier history/delistings and historical schemas; authentic delivery parsing remains unverified.
- Review abnormal-return flags against original sources; the versioned 50% diagnostic trigger is not a comprehensive anomaly detector or a strategy parameter.
- Decide acceptable gaps/staleness with official suspension/listing information. Current relative-history warnings do not establish completeness.
- Review adequate-sample/dependence and point-in-time adjustment methodology before a separate paper-research decision. The existing row bootstrap, STATIC hurdle and cohort breadth do not validate a strategy.
- Live Telegram delivery was not exercised. No real notifications were sent.

Next action: when execution is available, retain authenticated calendar/CM notice
bytes and real legacy/UDiFF checkpoints, reconcile dated identities and unsupported
restructurings, then measure complete historical coverage. The source inventory
is prepared; acquisition and historical pilot verification are not complete.
Passing software checks does not change the admission decision.
