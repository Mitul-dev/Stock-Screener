# Official NSE fixture and repeatable ingestion — 2026-10-20

The first implementation milestone is complete: an original official NSE EOD
fixture is retained, normalized, reconciled, and safely replayable. Full
20–30-stock pilot readiness remains **NOT READY** pending production integration.

## Official source evidence

- Listing: https://www.nseindia.com/all-reports
- Original bytes: `tests/fixtures/nse/BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv.zip`
- Download URL: https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv.zip
- Market date: 2026-10-08; acquired directly over HTTPS on 2026-10-20.
- Size: 208,947 bytes.
- SHA-256: `07fdfc3409b83fac6ee4a736ceb4fde20069c5d1a490d960b332c178cb703e39`.
- All 2,681 EQ rows (out of 3,733 total source rows) reconcile to original CSV
  identity, date, OHLCV and reported turnover fields using an independent CSV parser.
- RELIANCE has ISIN INE002A01018, close 1178, volume 13965493, reported turnover
  16539419460.40. That value differs from close multiplied by volume.
- This file has no delivery fields. Normalized delivery values remain null.

The adjacent `.zip.provenance.json` records original acquisition time, requested
and final URL, HTTP metadata, archive/member hashes, original columns and reference
rows. The retained ZIP was not transformed or repacked. Fixture authenticity rests
on acquisition from the official HTTPS archive; no digital signature is claimed.

## Implemented behavior

`NSEImporter.process_bhavcopy` preserves its existing API and adds optional
`source_url` and `downloaded_at` provenance. Raw inputs are archived by SHA-256;
processed names include input hash and parser revision. Receipts link raw/output
hashes, source identity, market dates, counts and acquisition metadata.

- Identical bytes reuse an intact output and receipt without rewriting either.
- Changed bytes at the same incoming filename create a separate preserved version.
- Raw/output corruption, incomplete artifact pairs and inconsistent deterministic
  receipt metadata cause explicit failure rather than automatic repair.
- HTML, unknown/malformed schemas, truncated ZIPs and multiple-CSV ZIP ambiguity
  publish no normalized output. Source bytes remain archived for diagnosis.
- Validation precedes publication and includes missing dates/identity, OHLCV,
  duplicate instrument/date keys, reported turnover and supplied delivery bounds.
- Absent, blank and untyped-null optional delivery remain null.
- Manifest appends retain older seven/eight-column records and are serialized by
  a filesystem lock. Complete new artifacts are published without replacing an
  existing destination; interrupted incomplete pairs fail closed on replay.

`scripts/fetch_official_nse_fixture.py` reacquires explicit date-specific files;
`scripts/import_nse_eod.py` imports local files and checks a supplied acquisition
receipt's input hash and size. No dependencies were added. Existing Yahoo pilot
files and prior outputs were preserved; the official import uses separate directories.

The existing Telegram unit test was reconciled with the already-implemented
requirement for frozen evidence. It now proves missing evidence is rejected and
an alert with a real snapshot remains idempotent, with no network delivery.

## Executed verification

Command:

```powershell
.venv\Scripts\python.exe -m pytest tests research/reviews/2026-09-28/test_v1_readiness.py -p no:cacheprovider -q --junitxml=research/reports/official_ingestion_tests_2026-10-20.xml
```

**70 collected, 70 passed** (57 current suite cases plus 13 original readiness
cases). One pre-existing CSV-provider Polars deprecation warning remains.
The fresh XML is `research/reports/official_ingestion_tests_2026-10-20.xml`.
The 19 replay-contract cases include corrupted artifacts/metadata, blank delivery,
changed inputs, malformed inputs and nine concurrent imports retaining all audit rows.
Four official-fixture tests independently reconcile the actual retained source.
The historical 17-case review suite was not modified or rerun in this milestone.

The import command was executed twice against the genuine fixture:

```powershell
.venv\Scripts\python.exe scripts/import_nse_eod.py tests/fixtures/nse/BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv.zip --provenance tests/fixtures/nse/BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv.zip.provenance.json
```

The manifest records PROCESSED then REUSED. The output hash and modification time
were unchanged on replay. Output SHA-256 is
`4ece8ee9cb331c28cabd573b4505c0632796b5365d29ae0f1f947b2becaeacf7`.
The machine-readable summary is `official_fixture_ingestion_2026-10-20.json`.

## Remaining scope

This proves one current official daily schema, not authentic delivery parsing,
corporate-action source integration, legacy historical coverage or a full cohort.
The production research runner still needs to preserve identifiers/turnover, apply
configured daily universe eligibility and execute its actual chronological partitions.
Event-level censoring/purging, complete trial/configuration/cost/boundary/input-hash
records and evidence eligibility remain outstanding. The dashboard still derives
data-quality validation from outcome-file presence, and mixed discovery/OOS data
can still satisfy an overly broad OOS flag.

The next implementation milestone is the existing production runner's integration.
No strategy thresholds, new strategies or ML were introduced. Paper research is
not approved.
