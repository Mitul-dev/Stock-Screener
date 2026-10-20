"""Run-bound Telegram preparation with explicit dry-run and delivery identities."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3

import requests

from equity_engine.evidence.run import RunEvidence


class TelegramAlerter:
    def __init__(self, db_path: str):
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.last_error = None
        # Preserve the historical outbox and migrate without replacing its rows.
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS outbox (
                alert_id TEXT PRIMARY KEY, instrument_id TEXT, setup TEXT,
                message TEXT, sent_at TIMESTAMP
            )
        """)
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(outbox)")}
        for column in ("run_id", "event_id", "snapshot_id", "delivery_mode"):
            if column not in columns:
                self.conn.execute(f"ALTER TABLE outbox ADD COLUMN {column} TEXT")
        self.conn.commit()

    def send_alert(self, alert_id: str, instrument_id: str, setup: str, message: str,
                   snapshot_id: str = None, *, manifest_path=None, event_time=None,
                   dry_run: bool = True) -> bool:
        """Require a run/event/date; select matching evidence strictly before the event.

        ``alert_id`` is the run's candidate event ID, never a snapshot ID. Repeats
        reverify artifacts before idempotent success. A dry run is recorded as
        DRY_RUN and can never suppress a subsequent explicitly requested send.
        """
        self.last_error = None
        if manifest_path is None or event_time is None:
            self.last_error = "An explicit run manifest and EOD event date are required"
            return False
        if not isinstance(dry_run, bool):
            self.last_error = "dry_run must be an explicit boolean"
            return False
        try:
            run = RunEvidence(manifest_path)
            identity, metadata = run.eligible_alert(alert_id, instrument_id, setup, event_time, snapshot_id)
        except Exception as error:
            self.last_error = str(error)
            return False
        run_id = run.manifest["trial_id"]
        mode = "DRY_RUN" if dry_run else "SENT"
        delivery_id = hashlib.sha256(json.dumps(
            [run_id, alert_id, identity, mode], separators=(",", ":")).encode("utf-8")).hexdigest()
        if self.conn.execute("SELECT 1 FROM outbox WHERE alert_id = ?", (delivery_id,)).fetchone():
            return True
        stats = metadata["statistics"]
        prepared = (f"{message}\n\nRun: {run_id}\nEvent: {alert_id}\nSnapshot: {identity}"
                    f"\nSetup: {setup}; partition: {metadata['partition']}; evidence cutoff: {metadata['data_cutoff']}"
                    f"\nAdjusted price basis cutoff: {metadata['price_basis_cutoff']}"
                    f"\nData quality: {run.quality_status}; engineering evidence only"
                    f"\nRecorded mean R: {stats.get('mean_r')}; statistical status: {stats.get('status')}"
                    f"\nLimitation: {stats.get('dependence_limitation', 'Sample dependence is not established.')}"
                    "\nPaper research is not approved.")
        for limitation in run.quality["limitations"]:
            prepared += f"\nQuality limitation: {limitation}"
        if not dry_run:
            if not self.bot_token or not self.chat_id:
                self.last_error = "Telegram credentials are unavailable"
                return False
            try:
                response = requests.post(f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                    json={"chat_id": self.chat_id, "text": prepared}, timeout=10)
                if response.status_code != 200 or response.json().get("ok") is not True:
                    self.last_error = "Telegram did not confirm delivery"
                    return False
            except Exception:
                self.last_error = "Telegram delivery failed"
                return False
        self.conn.execute("""
            INSERT INTO outbox (alert_id, instrument_id, setup, message, sent_at,
                                run_id, event_id, snapshot_id, delivery_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (delivery_id, instrument_id, setup, prepared, datetime.now(timezone.utc).isoformat(),
              run_id, alert_id, identity, mode))
        self.conn.commit()
        return True
