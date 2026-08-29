"""Lightweight file-backed alert feed for demo purposes.

Mức 1: mỗi lần một message gửi qua console tạo ra alert (alertFlg=true), lưu
lại 1 dòng vào file JSON cục bộ để xem tích lũy ở trang "Alert Log" — không
gộp case, không disposition. Đó là việc của Investigator (mức 2), để sau.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LOG_FILE = Path(__file__).resolve().parent / ".alert_log.json"


def _read_all() -> list[dict[str, Any]]:
    if not LOG_FILE.exists():
        return []
    try:
        with LOG_FILE.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def record_alert(entry: dict[str, Any]) -> None:
    """Append one alert entry to the log file."""

    entries = _read_all()
    entries.append(entry)
    with LOG_FILE.open("w", encoding="utf-8") as handle:
        json.dump(entries, handle, ensure_ascii=False, indent=2)


def load_alerts() -> list[dict[str, Any]]:
    """Return all recorded alerts, most recent first."""

    return list(reversed(_read_all()))


def clear_alerts() -> None:
    """Wipe the log file, e.g. to reset before a fresh demo run."""

    if LOG_FILE.exists():
        LOG_FILE.unlink()
