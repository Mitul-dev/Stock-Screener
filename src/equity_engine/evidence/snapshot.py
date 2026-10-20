import polars as pl
import json
import uuid
from datetime import datetime, date
from pathlib import Path
import hashlib
import io
import re

class EvidenceSnapshot:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.snapshots_dir = self.data_dir / "snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        
    def create_snapshot(
        self,
        setup_version: str,
        universe_version: str,
        methodology_version: str,
        data_cutoff: date,
        statistics: dict,
        outcomes_df: pl.DataFrame,
        **kwargs
    ) -> str:
        snapshot_id = kwargs.pop("snapshot_id", None) or str(uuid.uuid4())
        if not re.fullmatch(r"[A-Za-z0-9_-]+", snapshot_id):
            raise ValueError("Invalid snapshot identity")
        cutoff = date.fromisoformat(data_cutoff) if isinstance(data_cutoff, str) else data_cutoff
        for column in ("detection_date", "confirmation_date", "exit_date"):
            if column in outcomes_df.columns and outcomes_df.filter(pl.col(column) > cutoff).height:
                raise ValueError("Snapshot outcomes extend beyond its data cutoff")
        if kwargs.get("partition") and "partition" in outcomes_df.columns:
            if outcomes_df.filter(pl.col("partition").is_null() | (pl.col("partition") != kwargs["partition"])).height:
                raise ValueError("Snapshot outcomes must belong to its declared partition")
        outcomes_path = self.snapshots_dir / f"{snapshot_id}_outcomes.parquet"
        meta_path = self.snapshots_dir / f"{snapshot_id}_meta.json"
        if outcomes_path.exists() or meta_path.exists():
            raise FileExistsError("Snapshot identity already exists; refusing to overwrite evidence")
        buffer = io.BytesIO()
        outcomes_df.write_parquet(buffer)
        outcome_bytes = buffer.getvalue()
        computed_output_hash = hashlib.sha256(outcome_bytes).hexdigest()
        given_output_hash = kwargs.get("output_hash")
        if given_output_hash and given_output_hash != "pilot-output" and given_output_hash != computed_output_hash:
            raise ValueError("Supplied snapshot output hash does not match its outcomes")
        final_output_hash = computed_output_hash

        metadata = {
            "evidence_snapshot_id": snapshot_id,
            "setup_version": setup_version,
            "universe_version": universe_version,
            "methodology_version": methodology_version,
            "data_cutoff": data_cutoff.isoformat() if hasattr(data_cutoff, "isoformat") else str(data_cutoff),
            "created_at": datetime.now().isoformat(),
            "statistics": statistics,
            "configuration": kwargs.get("configuration", {}),
            "cost_model": kwargs.get("cost_model", {}),
            "date_boundaries": kwargs.get("date_boundaries", {}),
            "input_hash": kwargs.get("input_hash", ""),
            "output_hash": final_output_hash,
            "random_seed": kwargs.get("random_seed", 42)
        }
        metadata.update(kwargs)
        metadata["output_hash"] = final_output_hash
        metadata["outcomes_count"] = outcomes_df.height
        
        with outcomes_path.open("xb") as stream:
            stream.write(outcome_bytes)
        with open(meta_path, "x") as f:
            json.dump(metadata, f, indent=2)
            
        return snapshot_id
        
    def load_snapshot(self, snapshot_id: str, *, metadata_sha256=None,
                      outcomes_sha256=None) -> tuple[dict, pl.DataFrame]:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", snapshot_id):
            raise ValueError("Invalid snapshot identity")
        meta_path = self.snapshots_dir / f"{snapshot_id}_meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Snapshot metadata not found for {snapshot_id}")
        metadata_bytes = meta_path.read_bytes()
        if metadata_sha256 and hashlib.sha256(metadata_bytes).hexdigest() != metadata_sha256:
            raise ValueError(f"Snapshot metadata integrity error for {snapshot_id}")
        metadata = json.loads(metadata_bytes)
        if metadata.get("evidence_snapshot_id") != snapshot_id:
            raise ValueError(f"Snapshot identity mismatch for {snapshot_id}")
            
        outcomes_path = self.snapshots_dir / f"{snapshot_id}_outcomes.parquet"
        if outcomes_path.exists():
            outcome_bytes = outcomes_path.read_bytes()
            actual_hash = hashlib.sha256(outcome_bytes).hexdigest()
            recorded_hash = metadata.get("output_hash")
            if not recorded_hash or actual_hash != recorded_hash or (outcomes_sha256 and actual_hash != outcomes_sha256):
                raise ValueError(f"Snapshot integrity error: output_hash mismatch for {snapshot_id}")
            df = pl.read_parquet(io.BytesIO(outcome_bytes))
            if "outcomes_count" in metadata and df.height != metadata["outcomes_count"]:
                raise ValueError(f"Snapshot integrity error: outcome count mismatch for {snapshot_id}")
        else:
            raise FileNotFoundError(f"Snapshot outcomes missing for {snapshot_id}")
            
        return metadata, df
