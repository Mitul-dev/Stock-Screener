# Official NSE CM UDiFF fixture

`BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv.zip` contains the original bytes
downloaded directly from NSE's HTTPS archive. It has not been repacked, edited,
renamed, or generated from a third-party provider.

- Official report listing: https://www.nseindia.com/all-reports
- Direct archive URL: https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv.zip
- Acquisition time in UTC: `2026-10-20T04:23:25.690707+00:00`
- Market date: `2026-10-08`
- Size: `208947` bytes
- SHA-256: `07fdfc3409b83fac6ee4a736ceb4fde20069c5d1a490d960b332c178cb703e39`
- ZIP member: `BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv`

The adjoining `.zip.provenance.json` receipt records the requested and final
URLs, HTTP response metadata, acquisition timestamp, archive/member hashes,
original columns, source dates, counts, and verbatim reference rows. Receipt
hashes identify the retained bytes; authenticity is supported by acquisition
from the recorded official HTTPS host, rather than by an NSE digital signature.

## Observed schema and reconciliation anchors

The file has 3,733 rows, including 2,681 `EQ` rows, each with a distinct nonempty
ISIN. All rows have `TradDt` and `BizDt` equal to `2026-10-08`, `Sgmt=CM`, and
`Src=NSE`. Other security series are present and are not part of the current
EQ-series normalization boundary.

The real turnover column is `TtlTrfVal`. It contains reported traded value,
which must be retained directly; close multiplied by volume is not equivalent.
For example, the original `RELIANCE` row has:

| Field | Original value |
| --- | --- |
| `ISIN` | `INE002A01018` |
| `FinInstrmId` | `2885` |
| `OpnPric` | `1207.70` |
| `HghPric` | `1208.00` |
| `LwPric` | `1173.00` |
| `ClsPric` | `1178.00` |
| `TtlTradgVol` | `13965493` |
| `TtlTrfVal` | `16539419460.40` |

This fixture contains no delivery columns and no EQ rows with missing OHLC or
zero volume. It therefore verifies that delivery remains unavailable for this
input; it cannot prove parsing of an authentic delivery report or handling of
real zero-volume/missing-price examples. It also does not provide historical
coverage, corporate-action evidence, or a complete pilot cohort.

## Reacquisition

From the project folder:

```powershell
.venv\Scripts\python.exe scripts/fetch_official_nse_fixture.py --market-date 2026-10-08
```

The script uses only Python's standard library. It accepts the exact official
date-specific archive URL, checks the ZIP/member/header/source/date before
writing, limits the response size, and retains the received bytes unchanged.
Identical downloads reuse the fixture and original receipt. Different bytes at
an existing fixture path raise an explicit conflict instead of overwriting.
HTML responses and malformed or date-mismatched archives are rejected. Offline
tests consume this checked-in fixture without downloading data.
