import polars as pl
from pathlib import Path
import hashlib
from datetime import datetime, timezone
import zipfile
import io
import csv
import json
import os
import tempfile
from contextlib import contextmanager
from equity_engine.ingestion.validator import DataValidator

class NSEImporter:
    def __init__(self, raw_dir: str, processed_dir: str):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.raw_dir / "manifest.csv"
        
    def _update_manifest(self, source_file: Path, file_size: int, sha256: str, parser_version: str, status: str, market_date: str = None, error_msg: str = None, **provenance):
        with self._manifest_lock():
            self._append_manifest(source_file, file_size, sha256, parser_version,
                                  status, market_date, error_msg, **provenance)

    @contextmanager
    def _manifest_lock(self):
        # Serialize read/modify/write across importer instances and processes.
        with self.manifest_path.with_suffix(".lock").open("a+b") as stream:
            if not stream.seek(0, os.SEEK_END):
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _append_manifest(self, source_file: Path, file_size: int, sha256: str, parser_version: str, status: str, market_date: str = None, error_msg: str = None, **provenance):
        # Read strings so an older manifest with a blank error column remains
        # appendable. Import time and acquisition time have separate meanings.
        record = {
            "source_file": source_file.name,
            "market_date": market_date or "",
            "downloaded_at": provenance.get("downloaded_at") or "",
            "file_size": str(file_size),
            "sha256": sha256,
            "status": status,
            "parser_version": parser_version,
            "error": error_msg or "",
            "imported_at": datetime.now(timezone.utc).isoformat(),
            **{key: str(value) if value is not None else "" for key, value in provenance.items()},
        }
        rows, columns = [], []
        if self.manifest_path.exists():
            with self.manifest_path.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                columns = reader.fieldnames or []
                rows = list(reader)
        columns += [name for name in record if name not in columns]
        rows.append(record)
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
        self._atomic_replace(self.manifest_path, buffer.getvalue().encode("utf-8"))

    @staticmethod
    def _atomic_replace(path: Path, payload: bytes):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _publish_new(path: Path, payload: bytes):
        """Publish complete bytes without replacing an existing artifact."""
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _read_source(payload: bytes, path: Path) -> tuple[pl.DataFrame, str | None]:
        member = None
        if path.suffix.lower() == ".zip" or zipfile.is_zipfile(io.BytesIO(payload)):
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                members = [item for item in archive.infolist()
                           if not item.is_dir() and item.filename.lower().endswith(".csv")]
                if len(members) != 1:
                    raise ValueError("A Bhavcopy ZIP must contain exactly one CSV member")
                member = members[0].filename
                payload = archive.read(members[0])
        if payload.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"<"):
            raise ValueError("HTML/XML input is not a Bhavcopy report")
        return pl.read_csv(io.BytesIO(payload), infer_schema_length=10000), member

    def process_bhavcopy(self, file_path: str, *, source_url: str = None, downloaded_at: str | datetime = None) -> Path:
        """Validate and version an input by its bytes and parser revision.

        Receipts bind original bytes to normalized output. Replaying identical
        bytes reuses only an intact receipt/output pair. Unknown acquisition
        provenance remains absent rather than being inferred from import time.
        """
        path = Path(file_path)
        payload = path.read_bytes()
        file_size = len(payload)
        file_hash = hashlib.sha256(payload).hexdigest()
        parser_version, market_date_str = "UNKNOWN", None
        if isinstance(downloaded_at, datetime):
            downloaded_at = downloaded_at.isoformat()
        acquisition = {"source_url": source_url, "downloaded_at": downloaded_at}
        raw_path = self.raw_dir / "archive" / file_hash / path.name
        try:
            if raw_path.exists():
                if hashlib.sha256(raw_path.read_bytes()).hexdigest() != file_hash:
                    raise ValueError("Raw archive integrity error: input hash mismatch")
            else:
                self._publish_new(raw_path, payload)
            df, member = self._read_source(payload, path)
            source_rows = df.height
            if {"TckrSymb", "TradDt"} <= set(df.columns):
                parser_version = "NSE_CONSOLIDATED_V2"
                df = self._parse_consolidated(df)
            elif {"SYMBOL", "TIMESTAMP"} <= set(df.columns):
                parser_version = "NSE_LEGACY_V2"
                df = self._parse_legacy(df)
            else:
                raise ValueError(f"Unknown NSE Bhavcopy format in {path.name}")
            if df.is_empty():
                raise ValueError("Bhavcopy contains no EQ rows")
            df = df.with_columns(
                pl.lit(path.name).alias("source_file"),
                pl.col("date").cast(pl.String).alias("source_date"),
                pl.lit(file_hash).alias("source_sha256"),
            )
            DataValidator.validate_ohlcv(df)
            market_dates = df["date"].unique().sort().cast(pl.String).to_list()
            market_date_str = market_dates[0]
            parquet_path = self.processed_dir / f"normalized_{file_hash}_{parser_version}.parquet"
            receipt_path = self.processed_dir / "receipts" / f"{parquet_path.stem}.json"
            provenance = {**acquisition, "raw_path": str(raw_path.resolve()),
                          "processed_path": str(parquet_path.resolve()),
                          "receipt_path": str(receipt_path.resolve())}
            if parquet_path.exists() or receipt_path.exists():
                if not parquet_path.exists() or not receipt_path.exists():
                    raise ValueError("Processed integrity error: incomplete artifact/receipt pair")
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                if (receipt.get("input_sha256") != file_hash or
                        receipt.get("parser_version") != parser_version or
                        hashlib.sha256(parquet_path.read_bytes()).hexdigest() != receipt.get("output_sha256")):
                    raise ValueError("Processed integrity error: receipt or output hash mismatch")
                original_raw = Path(receipt["raw_path"])
                if not original_raw.is_file() or hashlib.sha256(original_raw.read_bytes()).hexdigest() != file_hash:
                    raise ValueError("Raw archive integrity error: receipt input missing or corrupted")
                expected_fields = {
                    "source_file": original_raw.name,
                    "archive_member": member,
                    "source_row_count": source_rows,
                    "row_count": df.height,
                    "excluded_non_eq_rows": source_rows - df.height,
                    "market_dates": market_dates,
                    "processed_path": str(parquet_path.resolve()),
                }
                expected_raw = self.raw_dir / "archive" / file_hash / original_raw.name
                if original_raw.resolve() != expected_raw.resolve() or any(
                    receipt.get(key) != value for key, value in expected_fields.items()
                ):
                    raise ValueError("Receipt integrity error: metadata does not match the source")
                self._update_manifest(path, file_size, file_hash, parser_version, "REUSED",
                                      market_date=market_date_str, **provenance)
                return parquet_path

            output = io.BytesIO()
            df.write_parquet(output)
            output_bytes = output.getvalue()
            receipt = {
                "input_sha256": file_hash,
                "output_sha256": hashlib.sha256(output_bytes).hexdigest(),
                "parser_version": parser_version,
                "source_file": path.name,
                "archive_member": member,
                "source_row_count": source_rows,
                "row_count": df.height,
                "excluded_non_eq_rows": source_rows - df.height,
                "market_dates": market_dates,
                "imported_at": datetime.now(timezone.utc).isoformat(),
                **provenance,
            }
            self._publish_new(parquet_path, output_bytes)
            self._publish_new(receipt_path, json.dumps(receipt, indent=2).encode("utf-8"))
            self._update_manifest(path, file_size, file_hash, parser_version, "PROCESSED",
                                  market_date=market_date_str, **provenance)
            return parquet_path
        except Exception as error:
            self._update_manifest(path, file_size, file_hash, parser_version, "FAILED",
                                  market_date=market_date_str, error_msg=str(error), **acquisition)
            if isinstance(error, (ValueError, FileExistsError)):
                raise
            raise ValueError(f"Failed to import {path.name}: {error}") from error
        
    def _parse_consolidated(self, df: pl.DataFrame) -> pl.DataFrame:
        if "SctySrs" in df.columns:
            df = df.filter(pl.col("SctySrs") == "EQ")
            
        normalized = df.select([
            pl.col("TradDt").str.strptime(pl.Date, "%Y-%m-%d").alias("date"),
            pl.col("ISIN").alias("instrument_id"),
            pl.lit("NSE").alias("exchange"),
            pl.col("TckrSymb").alias("symbol"),
            pl.col("SctySrs").alias("series"),
            pl.col("OpnPric").alias("open"),
            pl.col("HghPric").alias("high"),
            pl.col("LwPric").alias("low"),
            pl.col("ClsPric").alias("close"),
            pl.col("TtlTradgVol").alias("volume"),
            pl.col("TtlTrfVal").alias("traded_value")
        ])
        
        # Optional fields
        if "DlvblQty" in df.columns:
            normalized = normalized.with_columns(df["DlvblQty"].cast(pl.Float64).alias("deliverable_quantity"))
        else:
            normalized = normalized.with_columns(pl.lit(None).cast(pl.Float64).alias("deliverable_quantity"))
            
        if "DlvblPct" in df.columns:
            normalized = normalized.with_columns(df["DlvblPct"].cast(pl.Float64).alias("deliverable_pct"))
        else:
            normalized = normalized.with_columns(pl.lit(None).cast(pl.Float64).alias("deliverable_pct"))
            
        return normalized

    def _parse_legacy(self, df: pl.DataFrame) -> pl.DataFrame:
        df = df.filter(pl.col("SERIES") == "EQ")
        normalized = df.select([
            pl.col("TIMESTAMP").str.strptime(pl.Date, "%d-%b-%Y").alias("date"),
            pl.col("ISIN").alias("instrument_id"),
            pl.lit("NSE").alias("exchange"),
            pl.col("SYMBOL").alias("symbol"),
            pl.col("SERIES").alias("series"),
            pl.col("OPEN").alias("open"),
            pl.col("HIGH").alias("high"),
            pl.col("LOW").alias("low"),
            pl.col("CLOSE").alias("close"),
            pl.col("TOTTRDQTY").alias("volume"),
            pl.col("TOTTRDVAL").alias("traded_value")
        ])
        
        # Ensure optional delivery columns exist even if null
        normalized = normalized.with_columns(
            pl.lit(None).cast(pl.Float64).alias("deliverable_quantity"),
            pl.lit(None).cast(pl.Float64).alias("deliverable_pct")
        )
        return normalized
