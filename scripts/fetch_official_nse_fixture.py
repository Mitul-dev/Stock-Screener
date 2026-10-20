"""Retain an unchanged, authenticated-source NSE CM UDiFF fixture and its receipt.

Run explicitly; tests use the retained bytes and never require network access.
No data-provider fallback or data transformation is performed here.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date, datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import urllib.parse
import urllib.request
import zipfile


LISTING_URL = "https://www.nseindia.com/all-reports"
ARCHIVE_HOST = "nsearchives.nseindia.com"
MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024
REQUIRED_COLUMNS = {
    "TradDt", "BizDt", "Sgmt", "Src", "FinInstrmTp", "FinInstrmId", "ISIN",
    "TckrSymb", "SctySrs", "OpnPric", "HghPric", "LwPric", "ClsPric",
    "TtlTradgVol", "TtlTrfVal",
}


def official_url(market_date: date) -> str:
    filename = f"BhavCopy_NSE_CM_0_0_0_{market_date:%Y%m%d}_F_0000.csv.zip"
    return f"https://{ARCHIVE_HOST}/content/cm/{filename}"


def validate_archive(payload: bytes, market_date: date) -> dict:
    """Inspect received bytes without changing or extracting the archive."""
    if not payload.startswith(b"PK\x03\x04"):
        raise ValueError("Response is not a ZIP archive (HTML/errors are not fixtures).")
    expected_member = Path(urllib.parse.urlparse(official_url(market_date)).path).name[:-4]
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = archive.infolist()
        if len(members) != 1 or members[0].filename != expected_member:
            raise ValueError("Expected exactly the date-specific NSE CM UDiFF CSV member.")
        member = members[0]
        if member.file_size > MAX_DOWNLOAD_BYTES or member.flag_bits & 1:
            raise ValueError("Oversized or encrypted fixture member is unsupported.")
        csv_bytes = archive.read(member)  # CRC checked by zipfile.
        reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig")))
        columns = reader.fieldnames or []
        if not REQUIRED_COLUMNS.issubset(columns):
            raise ValueError(f"Missing UDiFF columns: {sorted(REQUIRED_COLUMNS - set(columns))}")
        rows = list(reader)
    if not rows:
        raise ValueError("Official fixture must contain rows.")
    for field, expected in (
        ("TradDt", market_date.isoformat()), ("BizDt", market_date.isoformat()),
        ("Sgmt", "CM"), ("Src", "NSE"),
    ):
        if {row[field] for row in rows} != {expected}:
            raise ValueError(f"Unexpected {field}; cannot verify the requested market date/source.")
    equities = [row for row in rows if row["SctySrs"] == "EQ"]
    if not equities:
        raise ValueError("Fixture must contain EQ-series rows.")
    return {
        "member_names": [member.filename],
        "members": [{
            "name": member.filename,
            "uncompressed_bytes": len(csv_bytes),
            "sha256": hashlib.sha256(csv_bytes).hexdigest(),
        }],
        "columns": columns,
        "row_count": len(rows),
        "eq_row_count": len(equities),
        "series_counts": dict(sorted(Counter(row["SctySrs"] for row in rows).items())),
        "source_dates": sorted({row["TradDt"] for row in rows}),
        "eq_missing_ohlc_count": sum(
            any(not row[field] for field in ("OpnPric", "HghPric", "LwPric", "ClsPric"))
            for row in equities
        ),
        "eq_zero_volume_count": sum(float(row["TtlTradgVol"] or 0) == 0 for row in equities),
        "eq_missing_isin_count": sum(not row["ISIN"] for row in equities),
        "delivery_columns_present": [name for name in columns if name in {"DlvblQty", "DlvblQtyPct"}],
        "reference_rows": [
            row for row in equities
            if row["TckrSymb"] in {"RELIANCE", "HDFCBANK", "INFY", "ITC", "TCS"}
        ],
    }


def fetch_fixture(market_date: date, destination: Path, url: str | None = None) -> dict:
    requested_url = url or official_url(market_date)
    expected_url = official_url(market_date)
    if requested_url != expected_url:
        raise ValueError(f"Use the official date-specific archive URL: {expected_url}")
    request = urllib.request.Request(requested_url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": LISTING_URL,
        "Accept": "application/zip, application/octet-stream",
    })
    with urllib.request.urlopen(request, timeout=45) as response:
        final_url = response.geturl()
        parsed_final = urllib.parse.urlparse(final_url)
        if parsed_final.scheme != "https" or parsed_final.hostname != ARCHIVE_HOST:
            raise ValueError("Download redirected outside the official HTTPS archive host.")
        payload = response.read(MAX_DOWNLOAD_BYTES + 1)
        if len(payload) > MAX_DOWNLOAD_BYTES:
            raise ValueError("Fixture download exceeds the allowed size.")
        response_headers = {
            key: response.headers.get(key)
            for key in ("Content-Type", "Content-Length", "ETag", "Last-Modified")
        }
    archive_details = validate_archive(payload, market_date)
    receipt = {
        "official_listing_url": LISTING_URL,
        "requested_url": requested_url,
        "final_url": final_url,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "market_date": market_date.isoformat(),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "http_status": 200,
        "response_headers": response_headers,
        **archive_details,
    }
    destination.mkdir(parents=True, exist_ok=True)
    archive_path = destination / Path(urllib.parse.urlparse(requested_url).path).name
    receipt_path = archive_path.with_suffix(archive_path.suffix + ".provenance.json")
    if archive_path.exists():
        if archive_path.read_bytes() != payload:
            raise FileExistsError("Official bytes differ from the retained fixture; refusing overwrite.")
    else:
        with archive_path.open("xb") as handle:
            handle.write(payload)
    if receipt_path.exists():
        previous = json.loads(receipt_path.read_text(encoding="utf-8"))
        if previous.get("sha256") != receipt["sha256"] or previous.get("market_date") != receipt["market_date"]:
            raise FileExistsError("Existing fixture receipt conflicts with downloaded content.")
        return previous  # Keep the original acquisition receipt on an identical replay.
    with receipt_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market-date", required=True, type=date.fromisoformat)
    parser.add_argument("--url", help="Optional explicit official date-specific URL; must match the date.")
    parser.add_argument(
        "--destination", type=Path,
        default=Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "nse",
    )
    args = parser.parse_args()
    receipt = fetch_fixture(args.market_date, args.destination, args.url)
    print(json.dumps({key: receipt[key] for key in (
        "requested_url", "downloaded_at_utc", "sha256", "bytes", "eq_row_count",
    )}, indent=2))


if __name__ == "__main__":
    main()
