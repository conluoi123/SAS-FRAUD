"""Lightweight file-backed alert feed for demo purposes.

Mức 1: mỗi lần một message gửi qua console tạo ra alert (alertFlg=true), lưu
lại 1 dòng vào file JSON cục bộ để xem tích lũy ở trang "Alert Log" — không
gộp case, không disposition. Đó là việc của Investigator (mức 2), để sau.
"""

from __future__ import annotations

import hashlib
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


def _deduplication_key(entry: dict[str, Any]) -> str:
    """Use factual request identifiers; never invent a correlation value."""

    transaction_id = str(entry.get("transaction_identifier") or "").strip()
    if transaction_id:
        return f"transaction:{transaction_id}"
    message_id = str(entry.get("message_identifier") or "").strip()
    if message_id:
        return f"message:{message_id}"
    canonical = {
        key: value
        for key, value in entry.items()
        if key not in {"recorded_at", "deduplication_key"}
    }
    encoded = json.dumps(
        canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return f"content:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def record_alert(entry: dict[str, Any]) -> bool:
    """Append one alert entry unless the same submitted request is already logged."""

    entries = _read_all()
    key = _deduplication_key(entry)
    if any(_deduplication_key(existing) == key for existing in entries):
        return False
    entries.append(dict(entry))
    temporary = LOG_FILE.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(entries, handle, ensure_ascii=False, indent=2)
    temporary.replace(LOG_FILE)
    return True


def load_alerts() -> list[dict[str, Any]]:
    """Return all recorded alerts, most recent first."""

    return list(reversed(_read_all()))


def clear_alerts() -> None:
    """Wipe the log file, e.g. to reset before a fresh demo run."""

    if LOG_FILE.exists():
        LOG_FILE.unlink()
