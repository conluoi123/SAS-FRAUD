"""Unit tests for the mức-1 file-backed alert feed."""

from __future__ import annotations

import importlib


def _fresh_alert_log(tmp_path, monkeypatch):
    module = importlib.import_module("app.streamlit_console.alert_log")
    log_file = tmp_path / ".alert_log.json"
    monkeypatch.setattr(module, "LOG_FILE", log_file)
    return module


def test_load_alerts_empty_when_no_file(tmp_path, monkeypatch) -> None:
    alert_log = _fresh_alert_log(tmp_path, monkeypatch)
    assert alert_log.load_alerts() == []


def test_record_alert_persists_and_loads_most_recent_first(tmp_path, monkeypatch) -> None:
    alert_log = _fresh_alert_log(tmp_path, monkeypatch)

    alert_log.record_alert({"transaction_identifier": "TXN-1"})
    alert_log.record_alert({"transaction_identifier": "TXN-2"})

    loaded = alert_log.load_alerts()
    assert [entry["transaction_identifier"] for entry in loaded] == ["TXN-2", "TXN-1"]


def test_clear_alerts_removes_file(tmp_path, monkeypatch) -> None:
    alert_log = _fresh_alert_log(tmp_path, monkeypatch)

    alert_log.record_alert({"transaction_identifier": "TXN-1"})
    assert alert_log.LOG_FILE.exists()

    alert_log.clear_alerts()
    assert not alert_log.LOG_FILE.exists()
    assert alert_log.load_alerts() == []


def test_load_alerts_tolerates_corrupt_file(tmp_path, monkeypatch) -> None:
    alert_log = _fresh_alert_log(tmp_path, monkeypatch)
    alert_log.LOG_FILE.write_text("not valid json", encoding="utf-8")

    assert alert_log.load_alerts() == []
