# Historical source preparation - 2026-10-20

Status: **PREPARED; ACQUISITION BLOCKED**.
Readiness: **NOT READY FOR REAL-DATA PILOT**. Paper research is not approved.

This step is based on `02915d7c1e292c2405f403810ecb369ad2f0e021`, the head of
still-unmerged draft PR #1. The new pull request targets that branch; it does not
merge PR #1 or imply its changes are on main.

## Concrete result

The exact existing 20-stock engineering cohort is now frozen with ISIN, source
security ID, company name and observation date directly from the original
retained NSE file. No symbols were replaced, historical validity ranges invented
or current identities substituted for earlier history. The cohort remains a
current-survivor engineering sample with explicit survivorship limitations.

A machine-readable inventory records a proposed 2023-01-01 to 2026-10-08 source
span, seven source families, 12 checkpoint requests and a complete 20-member
action/identity review queue. This window was chosen before inspecting any new
outcomes. Only the anchor session is retained. Expected/missing session counts
and usable historical partition boundaries remain null.

The source catalogue distinguishes inspected official document text from resolved
but unread CSV links and retained source bytes. It records 14 discovery sources.
Neither a complete calendar nor a corporate-action input feed is manufactured.
These JSON files describe preparation; the production runner does not consume
them or automatically enforce the inventory's unresolved gates.

Files added:

- `research/pilot/cohort_v1.json`
- `research/pilot/historical_inventory_v1.json`
- `research/pilot/source_catalog_2026-10-20.json`
- `research/pilot/verification_2026-10-20.json`
- `research/pilot/README.md`
- `docs/historical_sources.md`
- This report.

`BUILD_STATUS.md` records current acquisition limits separately from prior
software test execution. Runtime code, configuration, original fixtures and
frozen research artifacts are unchanged.

## Checks actually executed

The JavaScript code runtime was used in memory, independently of the unavailable
Python/execution workspace. Original ZIP bytes were fetched from the existing
GitHub fixture using its base64 file API. They were decoded and verified, not
re-downloaded from NSE or repacked.

| Check | Actual result |
|---|---|
| Original ZIP byte count and SHA-256 | 208,947 bytes; matches retained receipt |
| Original archive-member verification | Single named CSV; CRC-32 `12e2ccf7`; member SHA-256 matches receipt |
| Original CSV shape | 3,733 rows; all original columns match receipt |
| EQ source validation | 2,681 rows checked for date/source/identity, unique ISIN/date keys, finite positive OHLC and nonnegative volume/reported turnover |
| Cohort extraction | 20 unique EQ symbols and source ISINs; exact equality to previous smoke cohort |
| Derived inventory checks | Source fields, null historical validity, checkpoint/source references, unapproved factors and unknown calendar counts checked |

ZIP SHA-256:
`07fdfc3409b83fac6ee4a736ceb4fde20069c5d1a490d960b332c178cb703e39`.

CSV-member SHA-256:
`3bfb33cd4a0eb55b77ed2b24fd95cac6803edf00256bee65796ede4ee7549e53`.

The runtime SHA-256 implementation also passed the standard `abc` known-answer
check; both long source-byte digests and ZIP CRC matched the original receipt.
These are artifact/source-row checks, not execution of the Python importer,
pipeline, Streamlit application, research methodology or regression suite.

**Not executed in this step:** Python tests, archive downloads to disk, multi-year
ingestion, calendar derivation, historical production pilot or real Telegram
delivery. The execution workspace reports unavailable. The earlier 189-passing
test result belongs to PR #1 and is not claimed as a fresh run for this step.

## Findings that determine the acquisition path

The source guide links the actual official references. The following need
explicit treatment before historical pilot admission:

- NSE's reports listing distinguishes the legacy/UDiFF transition. The existing
  official downloader validates UDiFF only; an authentic legacy checkpoint and
  source-preserving legacy acquisition path are still needed.
- Official CM notices include Saturday live sessions. A weekday-only calendar,
  the set of downloaded bars, or clearing holidays cannot certify expected CM dates.
- Positive demerger cases exist within the proposed cohort/window. The current
  runner accepts SPLIT/BONUS only. Unsupported restructurings cannot be relabelled,
  ignored, or cleared merely because a price-return threshold is not triggered.
- Some located split/bonus notices contain multiple same-day components. Candidate
  factors remain unapproved until dated CM identities and original bars reconcile.
- Current source ISINs, mutable listing CSVs and the SecurityMaster class do not
  establish economic continuity across identifier changes. All 20 members still
  require full-interval action and identity review.
- Optional delivery and official index history are not acquired. Preserve null
  delivery/UNKNOWN regime and never use the older Yahoo files as official evidence.

The catalogue stores publication/ex-date/record/effective concepts separately.
Official derivatives-department notices are used only to cross-check underlying
equity actions; no F&O data, trading scope or contract logic is added.

## Reproduction when Python execution is available

The following read-only Python equivalent is supplied for reproduction. It was
not executed in this turn.

```python
from pathlib import Path
import csv
import hashlib
import io
import json
import zipfile

root = Path(".")
cohort = json.loads((root / "research/pilot/cohort_v1.json").read_text())
source = cohort["source"]
payload = (root / source["path"]).read_bytes()
assert len(payload) == source["bytes"]
assert hashlib.sha256(payload).hexdigest() == source["sha256"]
with zipfile.ZipFile(io.BytesIO(payload)) as archive:
    assert archive.namelist() == [source["member"]]
    member = archive.read(source["member"])  # zipfile verifies CRC
assert hashlib.sha256(member).hexdigest() == source["member_sha256"]
rows = list(csv.DictReader(io.StringIO(member.decode("utf-8-sig"))))
eq = [row for row in rows if row["SctySrs"] == "EQ"]
assert len(rows) == cohort["source_rows_total"] and len(eq) == 2681
fields = {"instrument_id": "ISIN", "source_security_id": "FinInstrmId",
          "company_name": "FinInstrmNm", "observed_on": "TradDt"}
for entry in cohort["members"]:
    selected = [row for row in eq if row["TckrSymb"] == entry["symbol"]]
    assert len(selected) == 1
    assert all(entry[key] == selected[0][column] for key, column in fields.items())
    assert entry["valid_from"] is None and entry["valid_to"] is None
print("Verified retained source and 20 observed cohort identities.")
```

The first live acquisition command and the calendar, raw-byte, legacy, action,
identity and index contracts are in [the source guide](../../docs/historical_sources.md).
After execution resumes, acquire real checkpoint/calendar/notice bytes before
extending to all expected sessions. Keep earlier runs and evidence intact.
Admission remains a separate decision after those source gates are verified.
