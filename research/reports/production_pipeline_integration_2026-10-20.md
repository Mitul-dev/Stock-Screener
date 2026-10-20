# Production pipeline integration — 2026-10-20

This milestone verifies actual source-preserving, configured chronological
production execution. Overall decision remains **NOT READY FOR REAL-DATA PILOT**
until the remaining source-history, quality and consumer gates are verified.
Paper research remains unapproved.

## Changes

- Original source identifiers, reported turnover, provenance and raw OHLCV remain
  present through adjustment, features, event audit and outcomes. No ticker-shaped
  ISIN is manufactured.
- The runner loads unchanged setup, universe, cost and regime YAML. Eligibility is
  evaluated on each candidate's own date; candidates excluded by turnover or purge
  gaps remain visible. Latest universe prices are ordered correctly and grouping
  uses instrument identity, including when a symbol is reused.
- Actual discovery, validation and holdout frames are passed to three actual
  backtest calls. Outcomes cannot read beyond their partition cutoff. Sparse
  instrument histories do not escape censoring merely because a market-date gap
  elapsed. Small datasets never reuse dates across partitions.
- Incomplete watches/holdings are censored and excluded from evidence. Completed
  trades and stopped losses remain eligible; zero-event runs have typed outputs.
- Split factors still apply if an ex-date bar is missing. Invalid factors, action
  identities/types and unsupported double adjustment fail explicitly.
- Configured costs are used, including GST on brokerage/exchange/SEBI components.
- Every run has persisted trial/configuration/cost/seed/boundary/input/config/code
  provenance and linked hashed output/snapshot files. Replays preserve earlier runs.
- Snapshots always have hashed Parquet, including zero-row files. Missing/corrupt
  bytes, cutoff violations and mismatched partition provenance fail. Statistics
  reject pooled partitions and the previous any-OOS-row loophole is closed.

No strategy thresholds, new strategies, ML or external alert delivery were added.
All four YAML files match their previous recorded SHA-256 values.

## Fresh automated verification

```powershell
.venv\Scripts\python.exe -m pytest tests research/reviews/2026-09-28/test_v1_readiness.py -p no:cacheprovider -q --junitxml=research/reports/production_pipeline_tests_2026-10-20.xml
```

**135 collected, 135 passed**: 122 current suite cases plus the 13 original readiness
cases. One pre-existing CSV-provider Polars deprecation warning remains. The XML
above records this execution. Historical review reports/test files were preserved;
their old 17-case suite was not treated as evidence for the new runner contract.

The 15 production acceptance cases invoke the actual entry point and wrap actual
implementations. They verify real split/backtest/snapshot inputs and outputs,
source identity/turnover, configured numeric net R including GST, separate setup
families, partition censoring, missing sessions, preserved terminal losses, all
lifecycle paths, zero events, run manifests, hashes, repeated-result equality,
and isolation of earlier decisions from changed future prices/turnover.

Additional helper/evidence tests cover short disjoint partitions, typed empties,
missing ex-date bars, invalid factors, unsorted identity-based universe input,
mixed-partition metrics and missing/tampered/cutoff-invalid snapshot artifacts.

## Persisted synthetic production example

The clearly synthetic 1,200-session acceptance dataset is retained under
`research/reports/production_acceptance_2026-10-20/synthetic_inputs/`.
Its run is `pilot-e963cbb8e3aa9ca5-bf9b48b2`; its full manifest and frozen evidence
are in the adjoining `synthetic_runs/` directory.

| Partition | Candidate outcomes evaluated | Completed eligible outcomes | Censored |
|---|---:|---:|---:|
| Discovery | 4 | 2 | 2 |
| Validation | 2 | 2 | 0 |
| Holdout | 2 | 2 | 0 |

Each partition contains one eligible BREAKOUT and one eligible VCB outcome.
There are 11 total candidates: eight evaluated and three illiquid candidates
excluded using their actual source turnover. Six separate snapshots are created.

Discovery ends 2020-10-05. The sparse-instrument event dated 2020-10-02 is censored
CONFIRMED; the boundary event dated 2020-10-05 is censored WATCH. Neither has an
exit or terminal R and neither appears in frozen evidence. Validation begins
2020-11-09. Outcome windows cannot run into it through the discovery backtest.

A separate production acceptance case generates FAILED, EXPIRED, INVALIDATED and
end-of-data WATCH records. Losses remain in evidence; expired/invalid/censored
records do not. This is separate from the retained base example above.

## Official 20-stock smoke check

The unchanged genuine NSE 2026-10-08 archive was run for the 20-stock cohort in
the original acquisition script. This produced 20 source rows for 20 distinct
source instrument IDs and completed successfully with zero events, typed empty
outputs and INSUFFICIENT EVIDENCE.

Run: `data/processed/pilot_runs/official_smoke/pilot-a8531e874c3e9b24-de0f1873/manifest.json`.
It records one discovery session and no validation/holdout sessions. Missing
corporate-action and index inputs are explicitly recorded. This one-day smoke
check is not evidence of a completed historical cohort or a tradable strategy.

The machine-readable summary `production_pipeline_verification_2026-10-20.json`
links both persistent examples, boundaries, counts and censored records.

## Remaining readiness gates

1. Assemble and validate genuine historical coverage for the fixed cohort, with
   sufficient feature warmup, evaluation windows and outcome follow-up.
2. Reconcile authentic corporate actions, delivery availability, instrument
   continuity and supported historical schemas.
3. Persist and review calendar gaps, stale records, abnormal returns, corporate
   action discontinuities and source completeness as data-quality results.
4. Connect dashboard and alerts to current run manifests, quality results and
   eligible frozen evidence. The dashboard currently still reads legacy output
   and derives data-quality validation from the presence of outcomes.
5. Decide adequate-sample/dependence methodology before any paper-research
   admission. The existing row bootstrap and minimum-block rule are not broad
   strategy validation. Regime breadth currently describes the supplied cohort.

The source adjustment basis cutoff is recorded separately from research partition
cutoffs. Raw execution values are retained; no blanket claim that every historical
adjusted absolute value was knowable at its event date is made.
