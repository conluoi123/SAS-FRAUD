"""Local processed-application history for the Application Fraud POC."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from .sas_client import SasRuntimeResponse
    from .sas_response import normalize_application_result
except ImportError:
    from sas_client import SasRuntimeResponse
    from sas_response import normalize_application_result


HISTORY_FILE = Path(__file__).resolve().parent / ".application_history.json"


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


def _read_all() -> list[dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []
    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return []
    return (
        [item for item in data if isinstance(item, dict)]
        if isinstance(data, list)
        else []
    )


def _deduplication_key(entry: dict[str, Any]) -> str:
    transaction_id = str(entry.get("transaction_id") or "").strip()
    if transaction_id:
        return f"transaction:{transaction_id}"

    request_json = entry.get("request_json")
    canonical = json.dumps(
        request_json,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"request:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def record_history(entry: dict[str, Any]) -> bool:
    """Persist one submitted application unless its stable key already exists."""

    entries = _read_all()
    key = _deduplication_key(entry)
    if any(_deduplication_key(existing) == key for existing in entries):
        return False

    stored = dict(entry)
    stored["deduplication_key"] = key
    entries.append(stored)
    temporary = HISTORY_FILE.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(entries, handle, ensure_ascii=False, indent=2)
    temporary.replace(HISTORY_FILE)
    return True


def load_application_history() -> list[dict[str, Any]]:
    """Return processed applications with the most recent record first."""

    return list(reversed(_read_all()))


def build_history_entry(
    payload: dict[str, Any],
    *,
    source: str,
    request_status: str,
    processed_at: str | None = None,
    http_status: int | None = None,
    duration_ms: int | None = None,
    parsed_response: Any = None,
    raw_response: str = "",
    parse_error: str | None = None,
    error_type: str = "",
    error_message: str = "",
) -> dict[str, Any]:
    """Build the factual history record from a sent payload and its response."""

    normalized = normalize_application_result(
        parsed_response,
        payload=payload,
        http_status=http_status,
        elapsed_ms=duration_ms,
        parse_error=parse_error,
    )
    message = payload.get("message", {}) if isinstance(payload, dict) else {}
    application = message.get("application", {}) if isinstance(message, dict) else {}
    applicant = message.get("applicant", {}) if isinstance(message, dict) else {}
    customer = message.get("customer", {}) if isinstance(message, dict) else {}

    return {
        "processed_at": processed_at or _utc_now(),
        "source": source,
        "application_id": normalized.application_id,
        "applicant_id": applicant.get("identifier"),
        "customer_id": normalized.customer_id,
        "customer_name": customer.get("surname") or applicant.get("name"),
        "application_type": application.get("type"),
        "requested_amount": application.get("amount"),
        "currency": application.get("currencyCode"),
        "channel": normalized.channel,
        "transaction_id": normalized.transaction_id,
        "message_id": normalized.message_id,
        "request_status": request_status,
        "decision": normalized.decision,
        "outcome_name": normalized.outcome_name,
        "rule_fired": normalized.rule_fired,
        "fired_rules": [rule.display_name for rule in normalized.fired_rules],
        "fired_rule_details": [rule.raw for rule in normalized.fired_rules],
        "alert_created": normalized.alert_created,
        "alert_reason": normalized.alert_reason,
        "alerted_entities": normalized.alerted_entities,
        "primary_alerted_entity": normalized.primary_alerted_entity,
        "primary_alerted_entity_type": normalized.primary_alerted_entity_type,
        "evidence": normalized.evidence,
        "http_status": http_status,
        "processing_duration_ms": duration_ms,
        "error_type": error_type,
        "error_message": error_message,
        "request_json": payload,
        "parsed_response": parsed_response,
        "raw_response": raw_response,
    }


def record_application_response(
    payload: dict[str, Any],
    response: SasRuntimeResponse,
    *,
    source: str,
    processed_at: str | None = None,
    request_status: str | None = None,
) -> bool:
    """Record one request that reached the Detection Runtime."""

    normalized = normalize_application_result(
        response.parsed_body,
        payload=payload,
        http_status=response.status_code,
        elapsed_ms=response.elapsed_ms,
        parse_error=response.parse_error,
    )
    status = request_status or (
        "Request successful" if normalized.request_ok else "Submission failed"
    )
    entry = build_history_entry(
        payload,
        source=source,
        request_status=status,
        processed_at=processed_at,
        http_status=response.status_code,
        duration_ms=response.elapsed_ms,
        parsed_response=response.parsed_body,
        raw_response=response.raw_body,
        parse_error=response.parse_error,
        error_type="Invalid JSON response" if response.parse_error else "",
        error_message=response.parse_error or "",
    )
    return record_history(entry)


def record_batch_history(
    results: list[dict[str, Any]],
    *,
    processed_at_factory: Callable[[], str] = _utc_now,
) -> int:
    """Record every actually submitted batch row and exclude invalid unsent rows."""

    recorded = 0
    for result in results:
        payload = result.get("_request")
        if (
            not isinstance(payload, dict)
            or result.get("requestStatus") == "Invalid payload"
        ):
            continue
        entry = build_history_entry(
            payload,
            source="batch",
            request_status=str(result.get("requestStatus") or "Submission failed"),
            processed_at=processed_at_factory(),
            http_status=result.get("httpStatus"),
            duration_ms=result.get("processingTimeMs"),
            parsed_response=result.get("_parsedResponse"),
            raw_response=str(result.get("_rawResponse") or ""),
            parse_error=(
                str(result.get("errorMessage") or "")
                if result.get("errorType") == "Invalid JSON response"
                else None
            ),
            error_type=str(result.get("errorType") or ""),
            error_message=str(result.get("errorMessage") or ""),
        )
        recorded += int(record_history(entry))
    return recorded


def record_guided_demo_history(
    results: list[dict[str, Any]],
    *,
    expected_step_count: int,
    processed_at: str | None = None,
) -> bool:
    """Record only a completed demo's final/current application, never its seeds."""

    if len(results) != expected_step_count or not results:
        return False
    final = results[-1]
    payload = final.get("payload")
    response = final.get("response")
    if not isinstance(payload, dict) or not isinstance(response, SasRuntimeResponse):
        return False
    return record_application_response(
        payload,
        response,
        source="guided_demo",
        processed_at=processed_at,
    )
