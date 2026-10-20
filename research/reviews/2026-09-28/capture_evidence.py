"""Read existing artifacts and save an independent review snapshot beside this file."""
import hashlib
import json
import runpy
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import polars as pl

from equity_engine.outcomes.engine import OutcomeEngine

ROOT = Path(__file__).resolve().parents[3]
DEST = Path(__file__).resolve().parent
SKIP = {".venv", ".git", "__pycache__", ".pytest_cache", ".hypothesis", "reviews"}


def main():
    files = []
    inventory = []
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT)
        if any(part in SKIP for part in rel.parts) or path.name == ".env":
            continue
        if path.is_dir():
            inventory.append(str(rel) + "/")
        else:
            payload = path.read_bytes()
            files.append({"path": str(rel), "size": len(payload),
                          "sha256": hashlib.sha256(payload).hexdigest()})
            inventory.append(str(rel))
    raw = pl.read_csv(ROOT / "data/raw/NSE_Pilot_Bhavcopy.csv")
    outcomes = pl.read_parquet(ROOT / "data/processed/pilot_outcomes.parquet")
    completed = outcomes.filter(pl.col("final_state") == "COMPLETED")
    states = Counter()
    original = OutcomeEngine.evaluate_event

    def record(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        states[result["final_state"]] += 1
        return result

    with patch.object(OutcomeEngine, "evaluate_event", record):
        runpy.run_path(str(ROOT / "tests/e2e/test_synthetic_e2e.py"))["test_synthetic_e2e"]()

    evidence = {
        "review_date": "2026-09-28", "root": str(ROOT),
        "existing_suite": {"passed": 26, "warnings": 1, "runtime_seconds": 5.48,
                           "note": "Recorded from independent pytest run; not rerun by this script."},
        "pilot_input": {
            "rows": raw.height, "symbols": raw["TckrSymb"].n_unique(),
            "distinct_dates": raw["TradDt"].n_unique(),
            "first_date": raw["TradDt"].min(), "last_date": raw["TradDt"].max(),
            "duplicate_symbol_date_rows": raw.height - raw.unique(["TckrSymb", "TradDt"]).height,
            "rows_matching_fabricated_isin_formula": raw.filter(
                pl.col("ISIN") == pl.concat_str([pl.lit("INE"), pl.col("TckrSymb"), pl.lit("01010")])).height,
            "invalid_isin_format_rows": raw.filter(
                ~pl.col("ISIN").str.contains(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")).height,
            "symbols_and_counts": raw.group_by("TckrSymb").len().sort("TckrSymb").to_dicts(),
            "session_coverage_note": "No independent exchange session calendar was available; row counts do not verify no missing sessions."
        },
        "saved_outcome_states": outcomes.group_by("final_state").len().sort("final_state").to_dicts(),
        "saved_completed_outcome_statistics": completed.select(
            pl.col("gross_realized_r").mean().alias("gross_mean_r"),
            pl.col("net_realized_r").mean().alias("net_mean_r"),
            pl.col("net_realized_r").median().alias("net_median_r"),
            pl.col("instrument_id").n_unique().alias("unique_instruments"),
            pl.col("detection_date").n_unique().alias("unique_detection_dates")).to_dicts()[0],
        "existing_synthetic_e2e_actual_outcome_states": dict(states),
        "files": files,
    }
    (DEST / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    (DEST / "repository_inventory.txt").write_text(
        "Application inventory; .venv, caches, .git, secrets and this review directory excluded.\n"
        + "\n".join(inventory) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in evidence.items() if k != "files"}, indent=2))


if __name__ == "__main__":
    main()
