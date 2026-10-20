# Current-run quality and evidence consumers — 2026-10-20

The dashboard and local alert preview now consume verified run manifests and
persisted quality results. Critical quality failures withhold frozen evidence.
Decision remains **NOT READY FOR REAL-DATA PILOT**. Paper research is not approved.

## Behavior and implementation

- `ingestion/quality.py` reuses `DataValidator` and persists 14 named engineering
  checks with counts, examples, limitations and blocking issues. Reports bind to
  trial, input/configuration/code hashes and run fingerprint. Optional supplied
  session calendars are hashed inputs; missing expected cohort sessions block
  evidence. Without a calendar, completeness is UNAVAILABLE.
- `run_pilot_pipeline.py` writes `quality.json` before frozen evidence. Missing
  cohort members, simultaneous symbol/identity ambiguity, invalid source identity
  and unexplained adjusted close moves of at least 50% are critical. Failed runs
  retain diagnostic outcomes with `evidence_eligible=False` and a withholding
  reason, empty statistics and no snapshots. Missing delivery stays null. Gaps,
  relative staleness and short history produce visible warnings; zero setups do
  not imply bad data or strategy validity. Four existing YAML files are unchanged.
- Version 2 manifests add the `run-relative-v1` path contract. Existing absolute
  paths remain historical metadata. The new shared `evidence/run.py` loads only
  run-local paths, rejects escapes, checks manifest/output/snapshot hashes and
  verifies identity, setup/version, partitions, cutoff, quality and statistics.
  `EvidenceSnapshot.load_snapshot` also accepts expected metadata/outcome hashes
  and reads verified bytes directly. Original frozen files were not rewritten.
- The Streamlit dashboard selects a current run and shows its actual quality,
  sources, partition boundaries, research status and frozen statistics. Missing
  quality is UNAVAILABLE; failed checks or corrupt runs never become VALIDATED
  merely because outcomes exist. Recorded statistical labels are explicitly
  distinguished from strategy/paper-research admission.
- `TelegramAlerter` requires a manifest and actual event/date/instrument/setup.
  It selects matching evidence with cutoff strictly before the event; a
  partition's end-of-period results cannot justify its earlier events. Requests
  default to DRY_RUN even with populated credentials. Repeats reverify the run;
  run/event/snapshot/mode identities preserve outbox idempotency. The old outbox
  schema is migrated without deleting rows. `TEST_ENV` no longer bypasses evidence.
- `scripts/preview_run_alerts.py` wires actual run candidates to this consumer and
  always uses dry-run mode. Tests mock the separate explicit delivery path; no
  actual Telegram requests were sent.
- CSV-provider date parsing uses explicit ISO `str.to_date` in both CSV methods,
  repairing the observed Polars 2.0 baseline failure without pinning away the issue.

Source files changed: production runner, new preview command, quality and shared
run loader, snapshot loader, dashboard, Telegram alerter and CSV provider. Tests:
new `tests/integration/test_run_consumers.py`, updated Telegram unit test. Docs:
BUILD_STATUS, README and pilot/data docs. Earlier reports and evidence remain intact.

## Actual execution

Checkout baseline: `ef91f777104ee647f25ed72b66fdfb8650142db4`. Only the handoff
commit follows the previously verified implementation baseline.

Setup used `python -m venv --system-site-packages .venv` and
`.venv/bin/python -m pip install -e '.[test]'`. Dependencies remain unpinned.
Actual Python/platform/dependency versions and unchanged configuration hashes
are recorded in `run_consumers_verification_2026-10-20.json`.

Baseline command was the same full selection below, before edits, with XML in
`run_consumers_baseline_tests_2026-10-20.xml`: **135 collected, 134 passed, one
failed**, with one Python SQLite timestamp-adapter warning. The failing CSV test
reports Polars 2.0 rejecting its removed string-to-date cast.

Relevant production/ingestion/evidence subset: **29 passed**. Consumer command:

```bash
TELEGRAM_BOT_TOKEN='' TELEGRAM_CHAT_ID='' .venv/bin/python -m pytest tests/integration/test_run_consumers.py tests/unit/test_telegram.py -p no:cacheprovider -q --junitxml=research/reports/run_consumers_tests_2026-10-20.xml
```

**55 collected, 55 passed**, 31.28 seconds, no warnings.

Final full command:

```bash
TELEGRAM_BOT_TOKEN='' TELEGRAM_CHAT_ID='' .venv/bin/python -m pytest tests research/reviews/2026-09-28/test_v1_readiness.py -p no:cacheprovider -q --junitxml=research/reports/run_consumers_full_tests_2026-10-20.xml
```

**189 collected, 189 passed**, 34.86 seconds, no warnings: 135 baseline cases plus
54 new consumer integration cases. Actual Streamlit testing exercises valid,
empty, missing-quality, failed-quality and corrupt-artifact views. Tests use
real production/frozen artifacts, moved runs, missing and changed bytes,
semantically mismatched metadata, wrong event identities/versions/dates, future
evidence, blocked candidates, failed quality and repeat-alert verification.

The historical September 17-case review suite, live Telegram delivery and live
NSE acquisition were not executed. No green-suite claim is made for them. All
production acceptance uses retained source bytes and offline inputs.

## Retained acceptance examples

Both fresh run directories are committed under
`research/reports/run_consumers_acceptance_2026-10-20/`. Their run-local hashes
verify after moving/copying them; no old absolute machine path is required.

| Example | Source rows/IDs | Candidates | Evaluated/eligible | Snapshots | Local dry runs |
|---|---:|---:|---:|---:|---:|
| Synthetic acceptance | 5,980 / 5 | 11 | 8 / 6 | 6 | 4 |
| Official 2026-10-08 smoke | 20 / 20 | 0 | 0 / 0 | 2 | 0 |

Both quality results are PASSED_WITH_WARNINGS. The synthetic run is EXPERIMENTAL;
its seven rejected previews include discovery events without earlier frozen
evidence and universe-ineligible candidates. The official run is INSUFFICIENT
EVIDENCE, explicitly warns of fewer than 252 sessions and has no later partitions.
It proves the single-day current-schema consumer path only.

Official fixture SHA-256 remains
`07fdfc3409b83fac6ee4a736ceb4fde20069c5d1a490d960b332c178cb703e39`.
Raw archives, input receipts, previous experiments and the original acceptance
bundle were preserved. The new bundle references retained input files and uses
run-local output references. Consumer hash checks verify run-local evidence;
external raw source authentication/reconciliation remains the import/review task.

Reproduce new synthetic artifacts with the existing retained inputs:

```bash
.venv/bin/python scripts/run_pilot_pipeline.py research/reports/production_acceptance_2026-10-20/synthetic_inputs/synthetic_nse.csv --corporate-actions research/reports/production_acceptance_2026-10-20/synthetic_inputs/actions.csv --index research/reports/production_acceptance_2026-10-20/synthetic_inputs/nifty.csv --output-dir data/processed/synthetic_consumer_runs
```

Inspect the committed portable run and prepare previews into a separate local DB:

```bash
.venv/bin/python scripts/preview_run_alerts.py research/reports/run_consumers_acceptance_2026-10-20/synthetic/manifest.json --outbox data/processed/consumer_preview.sqlite
.venv/bin/python -m streamlit run src/equity_engine/dashboard/app.py
```

Select `research/reports/run_consumers_acceptance_2026-10-20` as the dashboard runs
folder to inspect the two saved examples.

## Limits and next gate

PASSED_WITH_WARNINGS permits engineering evidence only. It does not establish
sufficient warmup/evaluation/follow-up, official calendar completeness, acceptable
suspensions/staleness, authentic delivery/legacy-schema parsing, official action
reconciliation, identity history or survivorship safety. Calendar input is caller
supplied, not automatically authenticated. Gaps before an instrument first appears
or after it disappears require source/history review. The 50% return threshold is
an explicit versioned review trigger, not a comprehensive anomaly detector.

Quality is assessed over the complete supplied run, not as an independently
reconstructed historical as-of quality decision. Adjusted absolute prices retain
the dataset basis cutoff; alerts show that cutoff. Raw prices remain separate.
Strict earlier evidence selection prevents using future outcome dates, but does
not close the broader point-in-time corporate-action methodology gate.

The existing row bootstrap, observation-count `effective_n`, STATIC hurdle and
adequate-sample/dependence limitations remain. No new strategies, ML, parameter
tuning, holdout optimization or trading-validity claims were introduced.

Next: inventory genuine historical NSE inputs and expected sessions for the fixed
20-stock smoke cohort, authenticate/reconcile corporate actions and identifiers,
and measure warmup, partition and follow-up coverage before a genuine historical
engineering pilot. A separate admission decision is still required.
