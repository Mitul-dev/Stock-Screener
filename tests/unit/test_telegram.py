from equity_engine.alerts.telegram import TelegramAlerter


def test_telegram_alerter(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_ENV", "1")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    alerter = TelegramAlerter(str(tmp_path / "alerts.db"))
    try:
        # Neither test mode nor a detached snapshot bypasses run verification.
        assert not alerter.send_alert("missing", "INST-1", "BREAKOUT", "Test message")
        assert not alerter.send_alert("A1", "INST-1", "BREAKOUT", "Test message", snapshot_id="detached")
        assert "run manifest" in alerter.last_error
        assert alerter.conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0
    finally:
        alerter.conn.close()
