# Historical source preparation

Status: **PREPARED; ACQUISITION BLOCKED**. This bundle freezes the existing
engineering cohort and records source work that can be reviewed before historical
downloads. It is not an acquired historical dataset or a pilot-admission decision.

| File | Purpose |
|---|---|
| `cohort_v1.json` | The unchanged 20-stock smoke cohort, independently extracted from the retained official ZIP. |
| `historical_inventory_v1.json` | Proposed dates, actual retained coverage, 12 checkpoint requests, action/identity review queues and blocking gates. |
| `source_catalog_2026-10-20.json` | Official links inspected and the exact distinction between read documents, resolved links and retained bytes. |
| `verification_2026-10-20.json` | Checks actually executed in the code runtime; Python/download checks not executed are explicit. |

The source ZIP and its original acquisition receipt remain under
`tests/fixtures/nse/`. No raw fixture, frozen research output, setup parameter,
cost, strategy or runtime source file is changed by this preparation.

The cohort is selected from current survivors for engineering. Its 2026-10-08
ISINs and security IDs are observations on that date, not invented historical
validity ranges. Every `valid_from` and `valid_to` remains null and historical
continuity remains UNVERIFIED. Do not substitute the current ISIN for all older
source identities, stitch reused symbols, or treat the cohort as a historical
membership universe.

The proposed 2023-01-01 through 2026-10-08 span is a source-coverage target chosen
without looking at any new outcomes. A full expected-session count is unknown.
The 12 checkpoints are requests, not a session calendar or proof that each archive
was downloaded. Only 2026-10-08 is retained and verified. No new historical market
dates were acquired in this step.

No `calendar.csv` or engine-ready corporate-action CSV is produced. Calendar
closures, subsequent amendments and special live sessions must be reconciled.
Known demergers cannot be disguised as supported split/bonus actions. Candidate
factors from notices remain unapproved until CM identities and raw bars reconcile.
The new JSON files are a preparation inventory; the production runner does not
load them or automatically enforce their unresolved gates.

See [the source guide](../../docs/historical_sources.md) and
[the milestone report](../reports/historical_source_preparation_2026-10-20.md).

Readiness: **NOT READY FOR REAL-DATA PILOT**. Paper research is not approved.
