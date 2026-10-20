# Data Management

## Raw Data Storage
The importer copies the exact input bytes to `raw_dir/archive/<sha256>/<original-name>`.
It never replaces that archived file and verifies its hash when the input is replayed.
The caller's incoming file can change; earlier archived versions remain available.
The old Yahoo-generated `data/raw/NSE_Pilot_Bhavcopy.csv` is not an official NSE fixture.

## Ingestion Architecture
1. **Acquisition**: `scripts/fetch_official_nse_fixture.py` downloads an explicit market date from the official NSE HTTPS archive and retains original ZIP bytes plus an acquisition receipt. Tests use retained fixtures offline.
2. **Normalizers**: `NSEImporter` parses varying formats and harmonizes them into a single schema.
3. **Validators**: `DataValidator` checks the schema for logical impossibility (e.g., negative volume, overlapping dates) before persisting.
4. **Publication**: Output names include the complete input SHA-256 and parser revision. A different input produces a separate output. An identical input reuses an intact output without rewriting it.
5. **Receipts**: `processed_dir/receipts/<output-stem>.json` links input/output hashes, archived source, member name, parser, row counts, market dates and supplied acquisition metadata.
6. **Manifest**: `raw_dir/manifest.csv` records PROCESSED, REUSED or FAILED attempts. Acquisition time is distinct from import time; unknown acquisition metadata remains empty. Existing seven/eight-column manifests are preserved and extended. A file lock serializes manifest appends.

## Verified Official Boundary

The retained original fixture is `tests/fixtures/nse/BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv.zip`.
Its acquisition receipt records the official URL and UTC acquisition time; its SHA-256 is
`07fdfc3409b83fac6ee4a736ceb4fde20069c5d1a490d960b332c178cb703e39`.
The CSV contains 3,733 rows, of which 2,681 are EQ series. All selected rows are
reconciled independently against original CSV values in the integration tests.
The actual `TtlTrfVal` value is preserved rather than estimated from close and volume.
No authentic delivery data is present in this fixture; its delivery columns remain null.
Legacy-format support remains available but has not yet been reconciled to a genuine legacy fixture.

The current import scope is EQ-series rows. Receipts count excluded non-EQ rows.
ZIP inputs must contain exactly one CSV member (case-insensitive); unrelated non-CSV
members are allowed. Unsupported or ambiguous archives and parsing/validation failures
are logged without publishing normalized output. Empty EQ results are rejected.

Validation includes OHLCV, duplicate instrument/date keys, missing dates/identity fields,
finite nonnegative reported turnover, and delivery bounds when supplied. Missing optional
delivery values remain null. New pilot runs persist engineering quality checks
in `quality.json`, including source identity, cohort gaps/staleness, adjusted-return
flags, optional calendar comparison and unavailable source/history gates.
Critical failures withhold evidence. Counts against the supplied cohort/calendar
do not certify official historical completeness or corporate-action reconciliation.
See `docs/pilot_pipeline.md` for the quality and consumer contract.

## Import and Replay

Run from the project folder:

```powershell
.venv\Scripts\python.exe scripts/import_nse_eod.py tests/fixtures/nse/BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv.zip --provenance tests/fixtures/nse/BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv.zip.provenance.json
```

The command verifies the acquisition receipt's hash/size, then imports into separate
`data/raw/official` and `data/processed/official` directories. Repeating it reuses the
same normalized file. `--raw-dir` and `--processed-dir` select other locations.

Direct API: `NSEImporter(raw_dir, processed_dir).process_bhavcopy(file_path,
source_url=..., downloaded_at=...)`. Existing calls without acquisition metadata work.
Identical bytes under a different incoming filename reuse the first artifact and its
original source filename/receipt; the additional attempt is recorded in the manifest.
Source URLs are supplied provenance, not an automatic authenticity certification.

Raw, output and deterministic receipt fields are verified before reuse. A missing or
corrupt pair is an integrity failure, never an invitation to overwrite evidence.
If publication is interrupted between output and receipt creation, preserve the
incomplete pair for inspection and use a fresh processed directory after verifying
the archived input, or restore the complete pair from a trusted backup. Atomic
publication requires a filesystem supporting hard links (verified on Windows NTFS).

## Canonical Internal Schema
```text
date: Date
instrument_id: str
exchange: str
symbol: str
series: str
open: float
high: float
low: float
close: float
volume: float
traded_value: float
deliverable_quantity: float | null
deliverable_pct: float | null
source_file: str
source_date: str
source_sha256: str
```

## Corporate Actions
Corporate actions (splits, bonuses) are kept in standalone raw formats.
`CorporateActionAdjustor` retains raw OHLCV and adds adjusted columns/factors before
features are calculated. End-to-end point-in-time handling, official action-source
reconciliation, and missing ex-date bars remain separate verification gates; this
single daily Bhavcopy fixture does not establish them.
