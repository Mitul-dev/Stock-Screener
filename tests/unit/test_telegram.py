import pytest
from datetime import date
import polars as pl
from equity_engine.alerts.telegram import TelegramAlerter
from equity_engine.evidence.snapshot import EvidenceSnapshot

def test_telegram_alerter(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_ENV", "1")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    
    db_file = tmp_path / "alerts.db"
    alerter = TelegramAlerter(str(db_file))
    
    try:
        # Evidence is required even in a local dry run.
        assert alerter.send_alert("missing", "INST-1", "BREAKOUT", "Test message") is False
        assert alerter.conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0
        snapshot_id = EvidenceSnapshot(str(tmp_path)).create_snapshot(
            "BREAKOUT", "test-universe", "test-methodology", date(2026, 10, 8),
            {"mean_r": 0.0, "status": "INSUFFICIENT EVIDENCE"},
            pl.DataFrame({"event_id": ["historical"], "net_realized_r": [0.0]}),
        )
        assert alerter.send_alert("A1", "INST-1", "BREAKOUT", "Test message", snapshot_id=snapshot_id)
        assert alerter.send_alert("A1", "INST-1", "BREAKOUT", "Test message", snapshot_id=snapshot_id)
        rows = alerter.conn.execute("SELECT * FROM outbox").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "A1"
        assert "INSUFFICIENT EVIDENCE" in rows[0][3]
    finally:
        alerter.conn.close()
