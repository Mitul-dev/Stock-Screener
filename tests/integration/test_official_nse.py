"""Offline integration proof using an unchanged ZIP acquired from official NSE.

These tests reconcile the retained source bytes independently of the importer's
parser. They establish one supported official daily schema, not historical
coverage or the availability of delivery data in this particular report.
"""

import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import zipfile

import polars as pl
import pytest

from equity_engine.ingestion.nse_importer import NSEImporter


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "nse"
    / "BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv.zip"
)
PROVENANCE = FIXTURE.with_name(FIXTURE.name + ".provenance.json")
ZIP_SHA256 = "07fdfc3409b83fac6ee4a736ceb4fde20069c5d1a490d960b332c178cb703e39"
CSV_MEMBER = "BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv"
MARKET_DATE = "2026-10-08"
OFFICIAL_URL = "https://nsearchives.nseindia.com/content/cm/" + FIXTURE.name


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def source_rows():
    # csv.DictReader is deliberately independent of the production Polars parser.
    with zipfile.ZipFile(FIXTURE) as archive:
        text = archive.read(CSV_MEMBER).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


@pytest.fixture
def official_import(tmp_path):
    raw = tmp_path / "raw"
    processed = tmp_path / "processed"
    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    importer = NSEImporter(str(raw), str(processed))
    output = importer.process_bhavcopy(
        str(FIXTURE),
        source_url=OFFICIAL_URL,
        downloaded_at=provenance["downloaded_at_utc"],
    )
    receipt_path = processed / "receipts" / f"{output.stem}.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    return raw, output, pl.read_parquet(output), receipt


def test_retained_official_zip_and_acquisition_provenance_match(source_rows):
    assert FIXTURE.stat().st_size == 208_947
    assert sha256(FIXTURE) == ZIP_SHA256
    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    assert provenance["requested_url"] == OFFICIAL_URL
    assert provenance["final_url"] == OFFICIAL_URL
    assert provenance["official_listing_url"] == "https://www.nseindia.com/all-reports"
    assert provenance["sha256"] == ZIP_SHA256
    assert provenance["bytes"] == 208_947
    assert provenance["market_date"] == MARKET_DATE
    assert provenance["http_status"] == 200
    assert provenance["downloaded_at_utc"]
    with zipfile.ZipFile(FIXTURE) as archive:
        assert archive.namelist() == [CSV_MEMBER]
        assert archive.testzip() is None
    assert len(source_rows) == 3_733
    assert sum(row["SctySrs"] == "EQ" for row in source_rows) == 2_681
    assert {row["TradDt"] for row in source_rows} == {MARKET_DATE}
    assert {row["Src"] for row in source_rows} == {"NSE"}
    assert "DlvblQty" not in source_rows[0]
    assert "DlvblPct" not in source_rows[0]


def test_every_official_eq_row_reconciles_to_normalized_market_fields(
    official_import, source_rows
):
    _, _, normalized, _ = official_import
    expected = {
        (row["ISIN"], row["TckrSymb"], row["SctySrs"], row["TradDt"]): row
        for row in source_rows
        if row["SctySrs"] == "EQ"
    }
    actual = {
        (row["instrument_id"], row["symbol"], row["series"], row["date"].isoformat()): row
        for row in normalized.to_dicts()
    }
    assert normalized.height == len(actual) == len(expected) == 2_681
    assert actual.keys() == expected.keys()
    numeric_fields = {
        "open": "OpnPric",
        "high": "HghPric",
        "low": "LwPric",
        "close": "ClsPric",
        "traded_value": "TtlTrfVal",
    }
    for key, source in expected.items():
        result = actual[key]
        assert result["date"] == date.fromisoformat(source["TradDt"])
        assert result["exchange"] == source["Src"] == "NSE"
        assert result["volume"] == int(source["TtlTradgVol"])
        for normalized_field, official_field in numeric_fields.items():
            assert result[normalized_field] == pytest.approx(
                float(source[official_field]), rel=1e-12, abs=1e-8
            ), (key, normalized_field)


def test_official_turnover_is_preserved_and_unavailable_delivery_stays_null(
    official_import,
):
    _, _, normalized, _ = official_import
    reliance = normalized.filter(pl.col("symbol") == "RELIANCE").row(0, named=True)
    assert reliance["instrument_id"] == "INE002A01018"
    assert reliance["close"] == 1_178.0
    assert reliance["volume"] == 13_965_493
    assert reliance["traded_value"] == pytest.approx(16_539_419_460.40)
    assert reliance["traded_value"] != pytest.approx(
        reliance["close"] * reliance["volume"]
    )
    assert normalized["deliverable_quantity"].null_count() == normalized.height
    assert normalized["deliverable_pct"].null_count() == normalized.height


def test_official_import_receipt_traces_original_bytes_and_actual_market_date(
    official_import,
):
    raw, output, normalized, receipt = official_import
    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    archived = Path(receipt["raw_path"])
    if not archived.is_absolute():
        archived = raw / archived
    assert archived == raw / "archive" / ZIP_SHA256 / FIXTURE.name
    assert archived.read_bytes() == FIXTURE.read_bytes()
    assert receipt["input_sha256"] == sha256(archived) == ZIP_SHA256
    assert receipt["output_sha256"] == sha256(output)
    assert receipt["row_count"] == 2_681
    assert receipt["market_dates"] == [MARKET_DATE]
    assert receipt["source_file"] == FIXTURE.name
    assert receipt["source_url"] == OFFICIAL_URL
    assert receipt["downloaded_at"] == provenance["downloaded_at_utc"]
    assert receipt["parser_version"]
    assert normalized["source_file"].unique().to_list() == [FIXTURE.name]
    assert normalized["source_date"].unique().to_list() == [MARKET_DATE]
    with (raw / "manifest.csv").open(encoding="utf-8", newline="") as stream:
        records = list(csv.DictReader(stream))
    assert len(records) == 1
    assert records[0]["status"] == "PROCESSED"
    assert records[0]["source_file"] == FIXTURE.name
    assert records[0]["market_date"] == MARKET_DATE
    assert records[0]["sha256"] == ZIP_SHA256
    # Processing must leave the retained official fixture untouched.
    assert sha256(FIXTURE) == ZIP_SHA256
