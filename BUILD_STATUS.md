# Build Status

Current milestone: PRODUCTION PIPELINE PARTITIONS AND PROVENANCE VERIFIED
Readiness: NOT READY FOR REAL-DATA PILOT
Last verified: 2026-10-20

## Verified implementation

- Original official NSE CM UDiFF ZIP for market date 2026-10-08 retained with URL, acquisition time, size and SHA-256.
- All 2,681 EQ rows reconciled to the source, including identifiers, OHLCV and reported turnover.
- Delivery fields remain null because this official file does not contain them.
- Content-addressed raw archives and processed output, immutable receipts, safe identical replay and separate changed-input versions.
- Corrupted raw/output/receipt artifacts rejected; malformed/HTML/ambiguous archives and invalid market fields rejected before publication.
- Older manifests remain readable; concurrent manifest appends retain their records.
- Production preserves original identifiers, reported turnover, source fields and raw/adjusted OHLCV through features, events and outcomes.
- Actual daily universe eligibility is applied on each candidate detection date using unchanged configured thresholds.
- The actual runner executes three bounded research partitions and keeps crossing/incomplete outcomes censored and outside evidence.
- Both setup families have separate partition-specific snapshots; stopped trades remain in eligible evidence.
- Loaded configuration/costs, GST, trial identity, input/config/code hashes, date boundaries and all artifact/snapshot links are persisted.
- Empty runs succeed with typed artifacts and INSUFFICIENT EVIDENCE. Snapshot files and hashes remain required even for zero rows.
- Official single-day production smoke check completed for 20 stocks; it does not establish historical pilot coverage.

## Fresh test execution

Command: `.venv\Scripts\python.exe -m pytest tests research/reviews/2026-09-28/test_v1_readiness.py -p no:cacheprovider -q`

Result: **135 collected, 135 passed**, one pre-existing Polars deprecation warning.
This includes 122 tests under `tests/` and 13 original readiness cases.
Fresh XML: `research/reports/production_pipeline_tests_2026-10-20.xml`.
The historical 17-case review suite was not rerun or modified in this milestone.
Passing these tests does not establish full production-pipeline readiness.

## Remaining gates

- Dashboard still reads legacy output and derives data-quality validation from a nonempty outcomes file; it must consume current run manifests and real quality checks.
- Alert consumers need end-to-end verification against run-scoped frozen evidence and matching setup/version eligibility.
- Adequate-sample/dependence methodology and paper-research admission remain separate decisions; mixed-partition/OOS contamination is now guarded.
- Authentic delivery ingestion, corporate-action source reconciliation and historical schema coverage remain unverified.
- A fixed 20–30-stock genuine historical cohort, calendar/gap/abnormal-return quality report and official-source full historical run remain outstanding.
- Regime breadth reflects eligible stocks in the supplied pilot cohort; VIX/source completeness is recorded and is not full-market evidence.

Next action: connect evidence consumers to current run manifests and persisted quality results, then validate genuine historical source coverage for the fixed cohort.
Paper research approval: NOT GRANTED.

See `research/reports/production_pipeline_integration_2026-10-20.md`, `docs/pilot_pipeline.md` and the earlier ingestion report for evidence and commands.
