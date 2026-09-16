"""Canonical payload synchronization for the Application Fraud workspace.

The form and JSON editor both operate on one effective payload.  Only verified
form-owned paths are patched when form values change, so JSON-only extensions
survive normal teller edits.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime
from typing import Any, Iterable, MutableMapping

try:
    from .application_validation import humanize_validation_errors
    from .payloads import validate_application_fraud_payload
except ImportError:
    from application_validation import humanize_validation_errors
    from payloads import validate_application_fraud_payload


PathPart = str | int
JsonPath = tuple[PathPart, ...]


# Paths owned by the business form.  Everything else belongs to the JSON editor
# and is deliberately preserved while these values are patched.
FORM_PAYLOAD_PATHS: tuple[JsonPath, ...] = (
    ("message", "solution", "originationType"),
    ("message", "solution", "activityType"),
    ("message", "solution", "authenticationType"),
    ("message", "solution", "channelType"),
    ("message", "solution", "customerType"),
    ("message", "request", "command"),
    ("message", "request", "decisioningInd"),
    ("message", "request", "schemaName"),
    ("message", "request", "messageClassificationName"),
    ("message", "request", "restResponseFlg"),
    ("message", "request", "messageDtTm"),
    ("message", "sas", "system", "transactionIdentifier"),
    ("message", "sas", "system", "messageDtTmUtc"),
    ("message", "application", "identifier"),
    ("message", "application", "type"),
    ("message", "application", "amount"),
    ("message", "application", "currencyCode"),
    ("message", "application", "channel"),
    ("message", "application", "purpose"),
    ("message", "application", "status"),
    ("message", "application", "stage"),
    ("message", "applicant", "identifier"),
    ("message", "applicant", "name"),
    ("message", "applicant", "monthlyRegularIncome"),
    ("message", "applicant", "outstandingDebt"),
    ("message", "applicant", "employment", 0, "employerName"),
    ("message", "applicant", "employment", 0, "status"),
    ("message", "customer", "identifier"),
    ("message", "customer", "surname"),
    ("message", "customer", "type"),
    ("message", "customer", "addressCountryCode"),
    ("message", "identification", "number"),
    ("message", "emailaddress", "fullEmail"),
    ("message", "phone", "full"),
    ("message", "location", "monthsAtLocation"),
    ("message", "device", "identifier"),
    ("message", "device", "ipAddress"),
    ("message", "appRisk", "bankId"),
    ("message", "appRisk", "salesAgentIdentifier"),
    ("message", "appRisk", "disbAcctNumber"),
    ("message", "appRisk", "referencePhone"),
    ("message", "appRisk", "normalizedAddress"),
    ("message", "appRisk", "disbAcctOwnerMatchInd"),
    ("message", "appRisk", "employerUnverifiedInd"),
)


FORM_STATE_PATHS: dict[str, JsonPath] = {
    "af_single_application_id": ("message", "application", "identifier"),
    "af_single_transaction_id": ("message", "sas", "system", "transactionIdentifier"),
    "af_form_application_type": ("message", "application", "type"),
    "af_form_application_amount": ("message", "application", "amount"),
    "af_form_currency": ("message", "application", "currencyCode"),
    "af_form_channel": ("message", "application", "channel"),
    "af_form_purpose": ("message", "application", "purpose"),
    "af_form_status": ("message", "application", "status"),
    "af_form_stage": ("message", "application", "stage"),
    "af_single_applicant_id": ("message", "applicant", "identifier"),
    "af_form_applicant_name": ("message", "applicant", "name"),
    "af_form_monthly_income": ("message", "applicant", "monthlyRegularIncome"),
    "af_form_outstanding_debt": ("message", "applicant", "outstandingDebt"),
    "af_form_employer_name": ("message", "applicant", "employment", 0, "employerName"),
    "af_form_employment_status": ("message", "applicant", "employment", 0, "status"),
    "af_single_customer_id": ("message", "customer", "identifier"),
    "af_form_customer_name": ("message", "customer", "surname"),
    "af_form_customer_type": ("message", "customer", "type"),
    "af_form_country": ("message", "customer", "addressCountryCode"),
    "af_single_identification_number": ("message", "identification", "number"),
    "af_form_email": ("message", "emailaddress", "fullEmail"),
    "af_single_phone": ("message", "phone", "full"),
    "af_form_months_at_location": ("message", "location", "monthsAtLocation"),
    "af_single_device_id": ("message", "device", "identifier"),
    "af_form_ip_address": ("message", "device", "ipAddress"),
    "af_form_bank_id": ("message", "appRisk", "bankId"),
    "af_single_sales_agent": ("message", "appRisk", "salesAgentIdentifier"),
    "af_single_disb_account": ("message", "appRisk", "disbAcctNumber"),
    "af_single_reference_phone": ("message", "appRisk", "referencePhone"),
    "af_single_normalized_address": ("message", "appRisk", "normalizedAddress"),
    "af_form_disb_owner_match": ("message", "appRisk", "disbAcctOwnerMatchInd"),
    "af_form_employer_verified": ("message", "appRisk", "employerUnverifiedInd"),
}


_MISSING = object()


def deep_get(root: Any, path: Iterable[PathPart], default: Any = None) -> Any:
    current = root
    for part in path:
        if isinstance(part, int):
            if not isinstance(current, list) or part >= len(current):
                return default
            current = current[part]
        else:
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
    return current


def deep_set(root: dict[str, Any], path: JsonPath, value: Any) -> None:
    current: Any = root
    for index, part in enumerate(path[:-1]):
        next_part = path[index + 1]
        if isinstance(part, int):
            while len(current) <= part:
                current.append({} if isinstance(next_part, str) else [])
            if not isinstance(current[part], (dict, list)):
                current[part] = {} if isinstance(next_part, str) else []
            current = current[part]
        else:
            expected = [] if isinstance(next_part, int) else {}
            if not isinstance(current, dict):
                raise TypeError(f"Cannot set path component {part!r}")
            if part not in current or not isinstance(current[part], type(expected)):
                current[part] = expected
            current = current[part]
    last = path[-1]
    if isinstance(last, int):
        while len(current) <= last:
            current.append(None)
        current[last] = copy.deepcopy(value)
    else:
        current[last] = copy.deepcopy(value)


def deep_delete(root: dict[str, Any], path: JsonPath) -> None:
    parent = deep_get(root, path[:-1], _MISSING)
    if parent is _MISSING:
        return
    last = path[-1]
    if isinstance(last, int) and isinstance(parent, list) and last < len(parent):
        parent.pop(last)
    elif isinstance(last, str) and isinstance(parent, dict):
        parent.pop(last, None)


def merge_form_payload(
    effective_payload: dict[str, Any],
    previous_form_payload: dict[str, Any],
    current_form_payload: dict[str, Any],
) -> dict[str, Any]:
    """Patch changed form-owned paths while preserving JSON-only content."""

    merged = copy.deepcopy(effective_payload)
    for path in FORM_PAYLOAD_PATHS:
        previous = deep_get(previous_form_payload, path, _MISSING)
        current = deep_get(current_form_payload, path, _MISSING)
        if previous == current:
            continue
        if current is _MISSING:
            deep_delete(merged, path)
        else:
            deep_set(merged, path, current)
    return merged


def parse_and_validate_payload(text: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as error:
        return None, [
            f"JSON không hợp lệ: {error.msg} "
            f"(dòng {error.lineno}, cột {error.colno})."
        ]
    if not isinstance(parsed, dict):
        return None, ["Message JSON phải là một JSON object."]
    errors = humanize_validation_errors(validate_application_fraud_payload(parsed))
    return (parsed if not errors else None), errors


def payload_to_form_updates(payload: dict[str, Any]) -> dict[str, Any]:
    """Map verified JSON paths back to Streamlit form state."""

    updates: dict[str, Any] = {}
    for state_key, path in FORM_STATE_PATHS.items():
        value = deep_get(payload, path, _MISSING)
        if value is _MISSING:
            continue
        if state_key == "af_form_disb_owner_match":
            value = bool(value)
        elif state_key == "af_form_employer_verified":
            value = not bool(value)
        updates[state_key] = value

    timestamp = deep_get(payload, ("message", "request", "messageDtTm"), None)
    if isinstance(timestamp, str):
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            pass
        else:
            updates["af_form_event_date"] = parsed.date()
            updates["af_form_event_time"] = parsed.time().replace(tzinfo=None)
    return updates


def apply_payload_to_state(
    payload: dict[str, Any], state: MutableMapping[str, Any]
) -> None:
    for key, value in payload_to_form_updates(payload).items():
        state[key] = value


def format_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
