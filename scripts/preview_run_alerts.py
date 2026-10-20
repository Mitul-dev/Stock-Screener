"""Prepare verified run alerts locally; this command never delivers to Telegram."""

import argparse
from pathlib import Path

from equity_engine.alerts.telegram import TelegramAlerter
from equity_engine.evidence.run import RunEvidence


def preview(manifest_path, *, outbox_path=None, event_id=None):
    run = RunEvidence(manifest_path)
    alerter = TelegramAlerter(str(outbox_path or run.root / "alerts_dry_run.sqlite"))
    results = []
    try:
        for event in run.frames["events"].iter_rows(named=True):
            if event_id is not None and event["event_id"] != event_id:
                continue
            accepted = alerter.send_alert(event["event_id"], event["instrument_id"], event["setup"],
                f"EOD research candidate: {event['symbol']} on {event['detection_date']}",
                manifest_path=manifest_path, event_time=event["detection_date"], dry_run=True)
            results.append({"event_id": event["event_id"], "dry_run_prepared": accepted,
                            "reason": alerter.last_error})
        if event_id is not None and not results:
            raise ValueError("Requested event is not present in the selected run")
    finally:
        alerter.conn.close()
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--outbox", type=Path)
    parser.add_argument("--event-id")
    args = parser.parse_args()
    for result in preview(args.manifest, outbox_path=args.outbox, event_id=args.event_id):
        print(result)
