"""Shared, read-only current-run verification for evidence consumers."""

from datetime import date, datetime
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re

import polars as pl

from equity_engine.evidence.snapshot import EvidenceSnapshot
from equity_engine.ingestion.quality import CHECK_NAMES, CRITICAL_CHECKS, QUALITY_VERSION


class RunIntegrityError(ValueError):
    pass


class RunEvidence:
    """Resolve portable run-local artifacts and verify their recorded provenance.

    Original absolute paths remain historical metadata. Only versioned relative
    paths are followed. Hashes detect changed bytes, not an authenticated author.
    """

    def __init__(self, manifest_path):
        self.path = Path(manifest_path).resolve()
        self.root = self.path.parent
        payload = self.path.read_bytes()
        expected = (self.root / "manifest.sha256").read_text(encoding="utf-8").strip()
        if hashlib.sha256(payload).hexdigest() != expected:
            raise RunIntegrityError("Run manifest hash mismatch")
        self.manifest = json.loads(payload)
        manifest = self.manifest
        if manifest.get("schema_version") != 2 or manifest.get("artifact_path_contract") != "run-relative-v1":
            raise RunIntegrityError("Legacy or unsupported run contract; recorded quality is unavailable. Generate a new run.")
        if manifest.get("execution_status") != "COMPLETED" or manifest.get("paper_research_approved") is not False:
            raise RunIntegrityError("Run did not complete")
        configuration_hash = hashlib.sha256(json.dumps(
            manifest["configuration"], sort_keys=True, indent=2, default=str).encode("utf-8")).hexdigest()
        if configuration_hash != manifest["configuration_hash"]:
            raise RunIntegrityError("Resolved configuration hash mismatch")
        input_hash = hashlib.sha256(json.dumps(sorted(
            (item["kind"], item["sha256"]) for item in manifest["inputs"]),
            sort_keys=True, indent=2, default=str).encode("utf-8")).hexdigest()
        if input_hash != manifest["input_hash"]:
            raise RunIntegrityError("Run input hash mismatch")
        expected_versions = [f"{family.split('_V')[0]}_V{settings['version']}"
                             for family, settings in manifest["configuration"]["setups"]["setups"].items()]
        if set(expected_versions) != set(manifest["setup_versions"]):
            raise RunIntegrityError("Run setup versions disagree with resolved configuration")
        self.frames = {}
        for name in ("features", "universe", "events", "outcomes", "regime"):
            self.frames[name] = pl.read_parquet(io.BytesIO(self._read_record(manifest["outputs"][name])))
        self.statistics = json.loads(self._read_record(manifest["outputs"]["statistics"]))
        self.quality = None
        self.quality_status = "UNAVAILABLE"
        quality_record = manifest["outputs"].get("quality")
        if quality_record is not None:
            # A declared but missing report is unavailable. Altered reports fail.
            try:
                quality_bytes = self._read_record(quality_record)
            except FileNotFoundError:
                quality_bytes = None
            if quality_bytes is not None:
                self.quality = json.loads(quality_bytes)
                self._verify_quality()
                self.quality_status = self.quality["status"]
        self.snapshots = {}
        manager = None
        for entry in manifest["snapshots"]:
            identity = entry["snapshot_id"]
            if not re.fullmatch(r"[A-Za-z0-9_-]+", identity) or identity in self.snapshots:
                raise RunIntegrityError("Invalid or duplicate snapshot identity")
            for key, suffix in (("metadata", "meta.json"), ("outcomes", "outcomes.parquet")):
                if entry[key].get("relative_path") != f"snapshots/{identity}_{suffix}":
                    raise RunIntegrityError("Snapshot artifact identity/path mismatch")
                self._resolve(entry[key])
            # Resolve before constructing the legacy manager, which creates its directory.
            if not (self.root / "snapshots").is_dir():
                raise FileNotFoundError("Run snapshot directory is missing")
            manager = manager or EvidenceSnapshot(str(self.root))
            metadata, frozen = manager.load_snapshot(identity,
                metadata_sha256=entry["metadata"]["sha256"], outcomes_sha256=entry["outcomes"]["sha256"])
            self._verify_snapshot(entry, metadata, frozen)
            self.snapshots[identity] = (metadata, frozen)

    def _resolve(self, record):
        relative = record.get("relative_path", "")
        candidate = PurePosixPath(relative)
        if not relative or candidate.is_absolute() or ".." in candidate.parts or "\\" in relative:
            raise RunIntegrityError("Invalid run-relative artifact path")
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise RunIntegrityError("Run artifact escapes its run directory")
        return path

    def _read_record(self, record):
        payload = self._resolve(record).read_bytes()
        if hashlib.sha256(payload).hexdigest() != record.get("sha256"):
            raise RunIntegrityError("Run artifact integrity/hash mismatch")
        return payload

    def _verify_quality(self):
        report, manifest = self.quality, self.manifest
        for field in ("trial_id", "input_hash", "configuration_hash", "code_hash", "run_fingerprint"):
            if report.get(field) != manifest.get(field):
                raise RunIntegrityError(f"Quality/run {field} mismatch")
        checks = report.get("checks", [])
        if (report.get("schema_version") != 1 or report.get("policy_version") != QUALITY_VERSION or
                len(checks) != len(CHECK_NAMES) or {check["name"] for check in checks} != CHECK_NAMES):
            raise RunIntegrityError("Incomplete or unsupported quality checks")
        blocking = [check["name"] for check in checks if check["blocking"]]
        if any(check["status"] not in {"PASSED", "WARNING", "FAILED", "UNAVAILABLE"} or
               (check["status"] == "FAILED") != check["blocking"] for check in checks):
            raise RunIntegrityError("Quality check status/blocking mismatch")
        required = CRITICAL_CHECKS | ({"calendar_completeness"} if any(
            item["kind"] == "calendar" for item in manifest["inputs"]) else set())
        if any(check["name"] in required and check["status"] not in {"PASSED", "FAILED"}
               for check in checks):
            raise RunIntegrityError("Critical quality checks are unavailable")
        status = "FAILED" if blocking else (
            "PASSED_WITH_WARNINGS" if any(check["status"] != "PASSED" for check in checks) else "PASSED")
        if (report.get("status") != status or report.get("blocking_issues") != blocking or
                report.get("evidence_allowed") is not (not blocking) or
                report.get("evidence_scope") != "ENGINEERING_ONLY" or
                report.get("paper_research_approved") is not False or
                manifest.get("quality_status") != status):
            raise RunIntegrityError("Inconsistent quality decision")

    def _verify_snapshot(self, entry, metadata, frozen):
        manifest = self.manifest
        for field in ("trial_id", "input_hash", "configuration_hash", "code_hash", "random_seed",
                      "methodology_version", "universe_version", "configuration", "cost_model", "date_boundaries"):
            if metadata.get(field) != manifest.get(field):
                raise RunIntegrityError(f"Snapshot/run {field} mismatch")
        for field in ("partition", "setup_version"):
            if metadata.get(field) != entry[field]:
                raise RunIntegrityError(f"Snapshot {field} mismatch")
        if entry["setup_version"] not in manifest["setup_versions"]:
            raise RunIntegrityError("Snapshot has an unknown setup version")
        if metadata.get("quality_sha256") != manifest["outputs"].get("quality", {}).get("sha256"):
            # A removed quality declaration cannot authorize evidence.
            if self.quality is not None:
                raise RunIntegrityError("Snapshot quality hash mismatch")
        boundary = manifest["date_boundaries"][entry["partition"]]
        cutoff = date.fromisoformat(metadata["data_cutoff"])
        if metadata["data_cutoff"] != boundary["end"] or metadata.get("price_basis_cutoff") != manifest["price_basis"]["cutoff"]:
            raise RunIntegrityError("Snapshot cutoff/basis mismatch")
        if frozen.height:
            invalid = frozen.filter(
                pl.col("setup").is_null() | (pl.col("setup") != entry["setup_version"]) |
                pl.col("partition").is_null() | (pl.col("partition") != entry["partition"]) |
                ~pl.col("evidence_eligible").fill_null(False) | pl.col("censored").fill_null(True) |
                pl.col("net_realized_r").is_null() | ~pl.col("net_realized_r").is_finite() |
                ~pl.col("final_state").is_in(["COMPLETED", "FAILED"]) |
                pl.col("detection_date").is_null() |
                (pl.col("detection_date") < date.fromisoformat(boundary["start"])))
            if invalid.height:
                raise RunIntegrityError("Snapshot contains ineligible or mismatched evidence rows")
            for column in ("detection_date", "confirmation_date", "exit_date"):
                if frozen.filter(pl.col(column).is_null() | (pl.col(column) > cutoff)).height:
                    raise RunIntegrityError("Snapshot evidence exceeds its cutoff or lacks terminal dates")
        matching = [item for item in self.statistics if item["partition"] == entry["partition"] and
                    item["setup_version"] == entry["setup_version"]]
        if len(matching) != 1 or matching[0]["statistics"] != metadata["statistics"]:
            raise RunIntegrityError("Snapshot statistics disagree with the run")

    def eligible_alert(self, event_id, instrument_id, setup_version, event_time, snapshot_id=None):
        """Use matching earlier evidence; partition-end hindsight cannot alert its own events."""
        if self.quality is None or not self.quality["evidence_allowed"]:
            raise RunIntegrityError(f"Run quality does not permit evidence: {self.quality_status}")
        if isinstance(event_time, datetime):
            raise ValueError("Use the source EOD event date, not a timestamp")
        day = date.fromisoformat(event_time) if isinstance(event_time, str) else event_time
        if not isinstance(day, date):
            raise ValueError("An explicit EOD event date is required")
        event = self.frames["events"].filter(pl.col("event_id") == event_id)
        if event.height != 1:
            raise RunIntegrityError("Alert event is absent or ambiguous in the run")
        row = event.row(0, named=True)
        if (row["instrument_id"] != instrument_id or row["setup"] != setup_version or
                row["detection_date"] != day or not row["universe_eligible"] or
                row["partition"] not in {"discovery", "validation", "holdout"} or row["exclusion_reason"]):
            raise RunIntegrityError("Alert event identity/setup/version/date/eligibility mismatch")
        boundary = self.manifest["date_boundaries"][row["partition"]]
        if not boundary["start"] or not boundary["end"] or not (
                date.fromisoformat(boundary["start"]) <= day <= date.fromisoformat(boundary["end"])):
            raise RunIntegrityError("Alert event lies outside its recorded partition")
        source = self.frames["features"].filter(
            (pl.col("instrument_id") == instrument_id) & (pl.col("date") == day))
        if source.height != 1 or source["source_sha256"][0] != row["source_sha256"]:
            raise RunIntegrityError("Alert event has no matching source bar")
        candidates = [(identity, metadata) for identity, (metadata, _) in self.snapshots.items()
                      if metadata["setup_version"] == setup_version and
                      date.fromisoformat(metadata["data_cutoff"]) < day]
        if snapshot_id is not None:
            candidates = [candidate for candidate in candidates if candidate[0] == snapshot_id]
        if not candidates:
            raise RunIntegrityError("No matching frozen evidence exists before the event date")
        return max(candidates, key=lambda item: (item[1]["data_cutoff"], item[0]))
