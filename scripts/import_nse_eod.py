"""Import a local NSE EOD CSV/ZIP, optionally with its acquisition receipt."""

import argparse
import hashlib
import json
from pathlib import Path

from equity_engine.ingestion.nse_importer import NSEImporter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--provenance", type=Path, help="Original acquisition JSON receipt")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/official"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/official"))
    args = parser.parse_args()
    acquisition = {}
    if args.provenance:
        metadata = json.loads(args.provenance.read_text(encoding="utf-8"))
        payload = args.input.read_bytes()
        if metadata.get("sha256") != hashlib.sha256(payload).hexdigest():
            parser.error("Acquisition receipt hash does not match input bytes")
        if metadata.get("bytes") != len(payload):
            parser.error("Acquisition receipt byte count does not match input")
        acquisition = {
            "source_url": metadata.get("final_url") or metadata.get("requested_url"),
            "downloaded_at": metadata.get("downloaded_at_utc"),
        }
    importer = NSEImporter(str(args.raw_dir), str(args.processed_dir))
    output = importer.process_bhavcopy(str(args.input), **acquisition)
    receipt = args.processed_dir / "receipts" / f"{output.stem}.json"
    print(json.dumps({"normalized": str(output.resolve()), "receipt": str(receipt.resolve())}, indent=2))


if __name__ == "__main__":
    main()
