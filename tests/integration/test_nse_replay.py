"""Synthetic contract tests for NSE ingestion; these are not official-data proof."""

import csv
import hashlib
import io
import json
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import zipfile

import polars as pl
import pytest

from equity_engine.ingestion.nse_importer import NSEImporter


FIELDS = [
    "TradDt", "TckrSymb", "ISIN", "SctySrs", "OpnPric", "HghPric",
    "LwPric", "ClsPric", "TtlTradgVol", "TtlTrfVal",
]


def source_bytes(*, close=102.0, delivery=False, blank_delivery=False):
    """Small invented rows deliberately contain turnover different from close*volume."""
    rows = [
        ["2026-10-15", "ALPHA", "SYNTH_ALPHA", "EQ", 100.0, 105.0, 99.0, close, 1000, 101234.50],
        ["2026-10-15", "BETA", "SYNTH_BETA", "EQ", 200.0, 205.0, 199.0, 202.0, 2000, 403211.25],
        ["2026-10-16", "ALPHA", "SYNTH_ALPHA", "EQ", 102.0, 106.0, 101.0, 104.0, 1200, 124567.75],
    ]
    fields = list(FIELDS)
    if delivery:
        fields += ["DlvblQty", "DlvblPct"]
        values = [["", ""]] * len(rows) if blank_delivery else [[400, 40.0], [1000, 50.0], [600, 50.0]]
        rows = [row + delivery_values for row, delivery_values in zip(rows, values)]
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(fields)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def setup_importer(tmp_path):
    raw = tmp_path / "raw"
    processed = tmp_path / "processed"
    incoming = tmp_path / "incoming"
    raw.mkdir()
    incoming.mkdir()
    return NSEImporter(str(raw), str(processed)), raw, processed, incoming


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt_for(processed, output):
    return json.loads((processed / "receipts" / f"{output.stem}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("delivery", [False, True], ids=["delivery-absent", "delivery-present"])
def test_receipt_traces_unchanged_input_and_normalized_market_fields(tmp_path, delivery):
    importer, raw, processed, incoming = setup_importer(tmp_path)
    source = incoming / "synthetic.csv"
    source.write_bytes(source_bytes(delivery=delivery))
    acquired = "2026-10-20T04:30:00+00:00"
    url = "https://example.invalid/synthetic-test-fixture.csv"

    output = importer.process_bhavcopy(str(source), source_url=url, downloaded_at=acquired)
    normalized = pl.read_parquet(output)
    receipt = receipt_for(processed, output)
    archived = Path(receipt["raw_path"])
    if not archived.is_absolute():
        archived = raw / archived

    assert archived == raw / "archive" / digest(source) / source.name
    assert archived.read_bytes() == source.read_bytes()
    assert receipt["input_sha256"] == digest(source)
    assert receipt["output_sha256"] == digest(output)
    assert receipt["parser_version"]
    assert receipt["row_count"] == 3
    assert receipt["source_file"] == source.name
    assert receipt["market_dates"] == ["2026-10-15", "2026-10-16"]
    assert receipt["source_url"] == url
    assert receipt["downloaded_at"] == acquired
    assert normalized["instrument_id"].to_list() == ["SYNTH_ALPHA", "SYNTH_BETA", "SYNTH_ALPHA"]
    assert normalized["traded_value"].to_list() == [101234.50, 403211.25, 124567.75]
    assert normalized["source_date"].to_list() == ["2026-10-15", "2026-10-15", "2026-10-16"]
    assert normalized["source_file"].to_list() == [source.name] * 3
    if delivery:
        assert normalized["deliverable_quantity"].to_list() == [400, 1000, 600]
        assert normalized["deliverable_pct"].to_list() == [40.0, 50.0, 50.0]
    else:
        assert normalized["deliverable_quantity"].null_count() == 3
        assert normalized["deliverable_pct"].null_count() == 3


def test_optional_delivery_columns_present_but_all_blank_are_null(tmp_path):
    importer, _, _, incoming = setup_importer(tmp_path)
    source = incoming / "blank-delivery.csv"
    source.write_bytes(source_bytes(delivery=True, blank_delivery=True))

    output = importer.process_bhavcopy(str(source))

    normalized = pl.read_parquet(output)
    assert normalized.height == 3
    assert normalized["deliverable_quantity"].null_count() == 3
    assert normalized["deliverable_pct"].null_count() == 3
    assert normalized["traded_value"].to_list() == [101234.50, 403211.25, 124567.75]


def test_identical_bytes_reuse_output_without_rewriting_for_either_filename(tmp_path):
    importer, _, processed, incoming = setup_importer(tmp_path)
    source = incoming / "first.csv"
    source.write_bytes(source_bytes())
    output = importer.process_bhavcopy(str(source))
    expected_hash = digest(output)
    sentinel_ns = 1_700_000_000_000_000_000
    os.utime(output, ns=(sentinel_ns, sentinel_ns))
    timestamp = output.stat().st_mtime_ns
    renamed = incoming / "renamed.csv"
    renamed.write_bytes(source.read_bytes())

    assert importer.process_bhavcopy(str(source)) == output
    assert importer.process_bhavcopy(str(renamed)) == output
    assert output.stat().st_mtime_ns == timestamp
    assert digest(output) == expected_hash
    assert list(processed.glob("*.parquet")) == [output]


def test_single_csv_zip_archives_the_original_container_and_reads_its_rows(tmp_path):
    importer, raw, processed, incoming = setup_importer(tmp_path)
    source = incoming / "synthetic.zip"
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("notes.txt", "Synthetic ingestion contract fixture")
        archive.writestr("nested/bhavcopy.csv", source_bytes())

    output = importer.process_bhavcopy(str(source))

    receipt = receipt_for(processed, output)
    assert receipt["input_sha256"] == digest(source)
    assert receipt["input_sha256"] != hashlib.sha256(source_bytes()).hexdigest()
    assert (raw / "archive" / digest(source) / source.name).read_bytes() == source.read_bytes()
    assert pl.read_parquet(output)["traded_value"].to_list() == [101234.50, 403211.25, 124567.75]
    assert receipt["row_count"] == 3


def test_changed_bytes_at_same_source_name_preserve_both_versions(tmp_path):
    importer, raw, _, incoming = setup_importer(tmp_path)
    source = incoming / "daily.csv"
    old_bytes = source_bytes(close=102.0)
    source.write_bytes(old_bytes)
    old_output = importer.process_bhavcopy(str(source))
    old_output_bytes = old_output.read_bytes()
    old_hash = hashlib.sha256(old_bytes).hexdigest()
    source.write_bytes(source_bytes(close=103.0))

    new_output = importer.process_bhavcopy(str(source))

    assert new_output != old_output
    assert old_output.read_bytes() == old_output_bytes
    assert (raw / "archive" / old_hash / source.name).read_bytes() == old_bytes
    assert (raw / "archive" / digest(source) / source.name).read_bytes() == source.read_bytes()
    assert pl.read_parquet(old_output)["close"][0] == 102.0
    assert pl.read_parquet(new_output)["close"][0] == 103.0


@pytest.mark.parametrize("artifact", ["raw", "processed"], ids=["corrupt-raw", "corrupt-output"])
def test_replay_rejects_corrupted_published_artifact_without_repairing_it(tmp_path, artifact):
    importer, raw, _, incoming = setup_importer(tmp_path)
    source = incoming / "daily.csv"
    source.write_bytes(source_bytes())
    output = importer.process_bhavcopy(str(source))
    target = raw / "archive" / digest(source) / source.name if artifact == "raw" else output
    damaged = b"deliberately corrupted immutable artifact"
    target.write_bytes(damaged)

    with pytest.raises((ValueError, OSError), match="(?i)(corrupt|integrity|hash|immutable)"):
        importer.process_bhavcopy(str(source))

    assert target.read_bytes() == damaged


@pytest.mark.parametrize(
    ("field", "damaged_value"),
    [("row_count", 999999), ("market_dates", ["1990-01-01"]), ("source_file", "different.csv")],
)
def test_replay_rejects_corrupted_receipt_metadata_without_rewriting(tmp_path, field, damaged_value):
    importer, raw, processed, incoming = setup_importer(tmp_path)
    source = incoming / "daily.csv"
    source.write_bytes(source_bytes())
    output = importer.process_bhavcopy(str(source))
    original_output = output.read_bytes()
    receipt_path = processed / "receipts" / f"{output.stem}.json"
    receipt = receipt_for(processed, output)
    receipt[field] = damaged_value
    damaged_receipt = json.dumps(receipt).encode("utf-8")
    receipt_path.write_bytes(damaged_receipt)

    with pytest.raises(ValueError, match="(?i)(integrity|receipt)"):
        importer.process_bhavcopy(str(source))

    assert receipt_path.read_bytes() == damaged_receipt
    assert output.read_bytes() == original_output
    with (raw / "manifest.csv").open(encoding="utf-8", newline="") as stream:
        records = list(csv.DictReader(stream))
    assert records[-1]["status"] == "FAILED"


def test_validation_failure_never_publishes_normalized_output(tmp_path):
    importer, raw, processed, incoming = setup_importer(tmp_path)
    source = incoming / "invalid-prices.csv"
    source.write_bytes(source_bytes(close=-1.0))

    with pytest.raises(ValueError):
        importer.process_bhavcopy(str(source))

    assert not list(processed.glob("*.parquet"))
    assert not list((processed / "receipts").glob("*.json"))
    with (raw / "manifest.csv").open(encoding="utf-8", newline="") as stream:
        records = list(csv.DictReader(stream))
    assert records[-1]["status"] == "FAILED"
    assert records[-1]["sha256"] == digest(source)
    assert records[-1]["error"]


@pytest.mark.parametrize("malformed", ["html", "unknown-csv", "truncated-zip", "ambiguous-zip"])
def test_unrecognized_or_ambiguous_input_is_logged_without_publication(tmp_path, malformed):
    importer, raw, processed, incoming = setup_importer(tmp_path)
    source = incoming / ("bad.zip" if "zip" in malformed else "bad.csv")
    if malformed == "html":
        source.write_bytes(b"<!DOCTYPE html><html><body>Access denied</body></html>")
    elif malformed == "unknown-csv":
        source.write_bytes(b"unrelated,value\nnot,a-bhavcopy\n")
    elif malformed == "truncated-zip":
        source.write_bytes(b"PK\x03\x04\x14\x00truncated archive")
    else:
        with zipfile.ZipFile(source, "w") as archive:
            archive.writestr("one.csv", source_bytes())
            archive.writestr("two.csv", source_bytes(close=103.0))

    with pytest.raises(ValueError):
        importer.process_bhavcopy(str(source))

    assert not list(processed.glob("*.parquet"))
    assert not list((processed / "receipts").glob("*.json"))
    with (raw / "manifest.csv").open(encoding="utf-8", newline="") as stream:
        records = list(csv.DictReader(stream))
    assert records[-1]["status"] == "FAILED"
    assert records[-1]["source_file"] == source.name
    assert records[-1]["sha256"] == digest(source)
    assert records[-1]["error"]


@pytest.mark.parametrize("has_error_column", [False, True], ids=["old-seven-columns", "old-eight-columns"])
def test_existing_manifest_schema_preserves_old_record_and_appends_result(tmp_path, has_error_column):
    importer, raw, _, incoming = setup_importer(tmp_path)
    fields = ["source_file", "market_date", "downloaded_at", "file_size", "sha256", "status", "parser_version"]
    if has_error_column:
        fields.append("error")
    old = dict(zip(fields[:7], ["old.csv", "2026-10-14", "2026-10-14T12:00:00", "123", "old-input-hash", "PROCESSED", "NSE_LEGACY"]))
    if has_error_column:
        old["error"] = ""
    with (raw / "manifest.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerow(old)
    source = incoming / "daily.csv"
    source.write_bytes(source_bytes())

    output = importer.process_bhavcopy(str(source))

    assert output.exists()
    with (raw / "manifest.csv").open(encoding="utf-8", newline="") as stream:
        records = list(csv.DictReader(stream))
    assert len(records) == 2
    assert all(records[0][key] == value for key, value in old.items())
    assert records[1]["source_file"] == source.name
    assert records[1]["status"] == "PROCESSED"
    assert records[1]["sha256"] == digest(source)


def test_concurrent_distinct_imports_retain_every_manifest_record(tmp_path):
    _, raw, processed, incoming = setup_importer(tmp_path)
    workers, rounds = 3, 3
    sources = []
    for worker in range(workers):
        group = []
        for iteration in range(rounds):
            source = incoming / f"source-{worker}-{iteration}.csv"
            source.write_bytes(source_bytes(close=100.0 + (worker * rounds + iteration) / 10))
            group.append(source)
        sources.append(group)
    starts = Barrier(workers)

    def import_group(group):
        importer = NSEImporter(str(raw), str(processed))
        outputs = []
        for source in group:
            starts.wait(timeout=10)
            outputs.append(importer.process_bhavcopy(str(source)))
        return outputs

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(import_group, group) for group in sources]
        outputs = [output for future in futures for output in future.result(timeout=30)]

    with (raw / "manifest.csv").open(encoding="utf-8", newline="") as stream:
        records = list(csv.DictReader(stream))
    assert len(outputs) == workers * rounds
    assert len(set(outputs)) == workers * rounds
    assert all(output.is_file() for output in outputs)
    assert len(records) == workers * rounds
    assert {record["source_file"] for record in records} == {source.name for group in sources for source in group}
    assert {record["sha256"] for record in records} == {digest(source) for group in sources for source in group}
    assert all(record["status"] == "PROCESSED" for record in records)
