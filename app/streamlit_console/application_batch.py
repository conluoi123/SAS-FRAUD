"""CSV validation and sequential execution for Application Fraud."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, MutableMapping

import requests

try:
    from .application_config import APPLICATION_CHANNELS
    from .payloads import (
        _utc_iso8601,
        build_application_fraud_payload,
        validate_application_fraud_payload,
    )
    from .sas_client import SasRuntimeResponse, send_message
    from .sas_response import extract_return_fields, summarize_sas_response
except ImportError:
    from application_config import APPLICATION_CHANNELS
    from payloads import (
        _utc_iso8601,
        build_application_fraud_payload,
        validate_application_fraud_payload,
    )
    from sas_client import SasRuntimeResponse, send_message
    from sas_response import extract_return_fields, summarize_sas_response


CSV_COLUMNS = (
    "messageDtTm",
    "applicationIdentifier",
    "applicationType",
    "applicationAmount",
    "currencyCode",
    "applicationChannel",
    "applicationPurpose",
    "applicationStatus",
    "applicationStage",
    "applicantIdentifier",
    "applicantName",
    "monthlyRegularIncome",
    "outstandingDebt",
    "employerName",
    "employmentStatus",
    "customerIdentifier",
    "customerSurname",
    "customerType",
    "addressCountryCode",
    "identificationNumber",
    "fullEmail",
    "phoneNumber",
    "monthsAtLocation",
    "deviceIdentifier",
    "ipAddress",
    "bankId",
    "salesAgentIdentifier",
    "disbAcctNumber",
    "referencePhone",
    "normalizedAddress",
    "disbAcctOwnerMatchInd",
    "employerUnverifiedInd",
)

CSV_REQUIRED_COLUMNS = (
    "messageDtTm",
    "applicationIdentifier",
    "applicationType",
    "applicationAmount",
    "currencyCode",
    "applicationChannel",
    "applicantIdentifier",
    "monthlyRegularIncome",
    "outstandingDebt",
    "customerIdentifier",
    "customerType",
    "addressCountryCode",
    "identificationNumber",
    "deviceIdentifier",
    "ipAddress",
    "bankId",
    "salesAgentIdentifier",
    "disbAcctNumber",
    "referencePhone",
    "normalizedAddress",
    "disbAcctOwnerMatchInd",
    "employerUnverifiedInd",
)

CSV_STRING_COLUMNS = {
    "applicationIdentifier",
    "applicantIdentifier",
    "customerIdentifier",
    "identificationNumber",
    "phoneNumber",
    "referencePhone",
    "disbAcctNumber",
    "deviceIdentifier",
    "salesAgentIdentifier",
    "transactionIdentifier",
}
CSV_BOOLEAN_COLUMNS = {"disbAcctOwnerMatchInd", "employerUnverifiedInd"}
CSV_NUMERIC_COLUMNS = {
    "applicationAmount",
    "monthlyRegularIncome",
    "outstandingDebt",
    "monthsAtLocation",
}
CSV_FIELD_MAX_LENGTHS = {"applicationIdentifier": 100, "transactionIdentifier": 36}
NULL_TOKENS = {"nan", "none", "null", "<na>"}
CSV_ALLOWED_COLUMNS = set(CSV_COLUMNS) | {"transactionIdentifier"}

RESULT_COLUMNS = (
    "rowNumber",
    "applicationIdentifier",
    "customerIdentifier",
    "applicationChannel",
    "solutionChannelType",
    "transactionIdentifier",
    "messageDtTm",
    "httpStatus",
    "requestStatus",
    "returnType",
    "decision",
    "firedFlg",
    "alertFlg",
    "firedRules",
    "processingTimeMs",
    "errorType",
    "errorMessage",
)
RESULT_EXPORT_COLUMNS = RESULT_COLUMNS + (
    "identificationNumber",
    "phoneNumber",
    "disbAcctNumber",
    "requestJson",
    "rawResponse",
)


@dataclass(frozen=True)
class CsvValidationResult:
    fingerprint: str
    columns: tuple[str, ...]
    rows: list[dict[str, str]]
    valid_rows: list[dict[str, str]]
    errors: list[dict[str, Any]]


def application_csv_template() -> bytes:
    """Return a header plus one small example row, encoded for Excel."""

    example = {
        "messageDtTm": "2026-09-09T08:00:00Z",
        "applicationIdentifier": "APP-000001",
        "applicationType": "PERSONAL_LOAN",
        "applicationAmount": "50000000",
        "currencyCode": "VND",
        "applicationChannel": "MOBILE_APP",
        "applicationPurpose": "PERSONAL_USE",
        "applicationStatus": "SUBMITTED",
        "applicationStage": "UNDER_REVIEW",
        "applicantIdentifier": "APL-000001",
        "applicantName": "Nguyen Van Demo",
        "monthlyRegularIncome": "25000000",
        "outstandingDebt": "5000000",
        "employerName": "Demo Company",
        "employmentStatus": "EMPLOYED",
        "customerIdentifier": "CUST-000001",
        "customerSurname": "Nguyen Van Demo",
        "customerType": "INDIVIDUAL",
        "addressCountryCode": "VN",
        "identificationNumber": "079099009999",
        "fullEmail": "demo.application@example.com",
        "phoneNumber": "0901234567",
        "monthsAtLocation": "24",
        "deviceIdentifier": "DEV-APP-000001",
        "ipAddress": "203.0.113.42",
        "bankId": "BANK-A",
        "salesAgentIdentifier": "SALES-001",
        "disbAcctNumber": "09704000012345",
        "referencePhone": "0912345678",
        "normalizedAddress": "88 CONG HOA TP HCM",
        "disbAcctOwnerMatchInd": "1",
        "employerUnverifiedInd": "0",
    }
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerow(example)
    return output.getvalue().encode("utf-8-sig")


def _error(
    row_number: int,
    column_name: str,
    value: Any,
    reason: str,
    *,
    severity: str = "Error",
) -> dict[str, Any]:
    return {
        "rowNumber": row_number,
        "columnName": column_name,
        "value": "" if value is None else str(value),
        "severity": severity,
        "reason": reason,
    }


def _parse_bool(value: Any) -> int:
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return 1
    if normalized in {"0", "false", "no", "n"}:
        return 0
    raise ValueError("must be boolean (0/1, true/false, yes/no)")


def _number(value: Any, *, integer: bool = False) -> int | float | None:
    source = str(value or "").strip()
    if not source:
        return None
    parsed = float(source)
    if not math.isfinite(parsed):
        raise ValueError("must be a finite number")
    if integer:
        if not parsed.is_integer():
            raise ValueError("must be an integer")
        return int(parsed)
    return parsed


def _text(row: dict[str, str], column: str) -> str | None:
    value = str(row.get(column, "") or "").strip()
    return value or None


def map_application_csv_row(row: dict[str, str]) -> dict[str, Any]:
    """Map one validated CSV row to the existing payload builder input."""

    values = {
        "message_datetime": _text(row, "messageDtTm"),
        "application_identifier": _text(row, "applicationIdentifier"),
        "transaction_identifier": _text(row, "transactionIdentifier"),
        "application_type": _text(row, "applicationType"),
        "application_amount": _number(row.get("applicationAmount")),
        "currency_code": _text(row, "currencyCode"),
        "application_channel": _text(row, "applicationChannel"),
        "application_purpose": _text(row, "applicationPurpose"),
        "application_status": _text(row, "applicationStatus"),
        "application_stage": _text(row, "applicationStage"),
        "applicant_identifier": _text(row, "applicantIdentifier"),
        "applicant_name": _text(row, "applicantName"),
        "monthly_regular_income": _number(row.get("monthlyRegularIncome")),
        "outstanding_debt": _number(row.get("outstandingDebt")),
        "employer_name": _text(row, "employerName"),
        "employment_status": _text(row, "employmentStatus"),
        "customer_identifier": _text(row, "customerIdentifier"),
        "customer_name": _text(row, "customerSurname"),
        "customer_type": _text(row, "customerType"),
        "address_country_code": _text(row, "addressCountryCode"),
        "identification_number": _text(row, "identificationNumber"),
        "email": _text(row, "fullEmail"),
        "phone": _text(row, "phoneNumber"),
        "months_at_location": _number(row.get("monthsAtLocation"), integer=True),
        "device_identifier": _text(row, "deviceIdentifier"),
        "device_ip_address": _text(row, "ipAddress"),
        "app_risk": {
            "bankId": _text(row, "bankId"),
            "salesAgentIdentifier": _text(row, "salesAgentIdentifier"),
            "disbAcctNumber": _text(row, "disbAcctNumber"),
            "referencePhone": _text(row, "referencePhone"),
            "normalizedAddress": _text(row, "normalizedAddress"),
            "disbAcctOwnerMatchInd": _parse_bool(
                row.get("disbAcctOwnerMatchInd")
            ),
            "employerUnverifiedInd": _parse_bool(
                row.get("employerUnverifiedInd")
            ),
        },
    }
    return build_application_fraud_payload(values)


def parse_application_csv(data: bytes) -> CsvValidationResult:
    """Parse as strings, validate the whole file, and identify sendable rows."""

    fingerprint = hashlib.sha256(data).hexdigest()
    errors: list[dict[str, Any]] = []
    if not data or not data.strip():
        return CsvValidationResult(
            fingerprint, (), [], [], [_error(0, "file", "", "CSV file is empty")]
        )
    try:
        source = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        return CsvValidationResult(
            fingerprint,
            (),
            [],
            [],
            [_error(0, "file", "", f"CSV must use UTF-8 encoding: {error}")],
        )

    reader = csv.reader(io.StringIO(source, newline=""))
    try:
        raw_header = next(reader)
    except StopIteration:
        return CsvValidationResult(
            fingerprint, (), [], [], [_error(0, "file", "", "CSV file is empty")]
        )
    header = [item.strip() for item in raw_header]
    duplicates = sorted({name for name in header if header.count(name) > 1 and name})
    for name in duplicates:
        errors.append(_error(1, name, name, "Duplicate CSV header"))
    for name in CSV_REQUIRED_COLUMNS:
        if name not in header:
            errors.append(_error(1, name, "", "Required column is missing"))
    for name in header:
        if name and name not in CSV_ALLOWED_COLUMNS:
            errors.append(
                _error(
                    1,
                    name,
                    name,
                    "Unsupported CSV column; no verified Application Fraud path",
                )
            )

    rows: list[dict[str, str]] = []
    for row_number, fields in enumerate(reader, start=2):
        if not fields or not any(str(value).strip() for value in fields):
            errors.append(_error(row_number, "row", "", "Blank row"))
            continue
        if len(fields) != len(header):
            errors.append(
                _error(
                    row_number,
                    "row",
                    "",
                    f"Expected {len(header)} values but found {len(fields)}",
                )
            )
        normalized_fields = fields[: len(header)] + [""] * max(0, len(header) - len(fields))
        row = {name: value.strip() for name, value in zip(header, normalized_fields)}
        row["_rowNumber"] = str(row_number)
        rows.append(row)
    if not rows:
        errors.append(_error(0, "file", "", "CSV contains no data rows"))

    seen_applications: dict[str, int] = {}
    seen_transactions: dict[str, int] = {}
    for row in rows:
        row_number = int(row["_rowNumber"])
        for column, value in row.items():
            if column.startswith("_"):
                continue
            if value.strip().lower() in NULL_TOKENS:
                errors.append(
                    _error(row_number, column, value, "Literal null/NaN is not allowed")
                )
        for column in CSV_REQUIRED_COLUMNS:
            if column in header and not row.get(column, "").strip():
                errors.append(_error(row_number, column, "", "Required value is empty"))

        application_id = row.get("applicationIdentifier", "").strip()
        if application_id:
            if application_id in seen_applications:
                errors.append(
                    _error(
                        row_number,
                        "applicationIdentifier",
                        application_id,
                        "Duplicate application ID; first seen on row "
                        f"{seen_applications[application_id]}",
                    )
                )
            else:
                seen_applications[application_id] = row_number
        transaction_id = row.get("transactionIdentifier", "").strip()
        if transaction_id:
            if transaction_id in seen_transactions:
                errors.append(
                    _error(
                        row_number,
                        "transactionIdentifier",
                        transaction_id,
                        "Duplicate transaction ID; first seen on row "
                        f"{seen_transactions[transaction_id]}",
                    )
                )
            else:
                seen_transactions[transaction_id] = row_number

        timestamp = row.get("messageDtTm", "")
        if timestamp:
            try:
                _utc_iso8601(timestamp)
            except ValueError:
                errors.append(
                    _error(row_number, "messageDtTm", timestamp, "Invalid ISO-8601 timestamp")
                )
        channel = row.get("applicationChannel", "").strip().upper()
        if channel and channel not in APPLICATION_CHANNELS:
            errors.append(
                _error(
                    row_number,
                    "applicationChannel",
                    channel,
                    "Channel is outside APPLICATION_CHANNELS",
                )
            )
        for column in CSV_NUMERIC_COLUMNS:
            value = row.get(column, "").strip()
            if not value:
                continue
            try:
                number = float(value)
                if not math.isfinite(number) or number < 0:
                    raise ValueError
                if column == "monthsAtLocation" and not number.is_integer():
                    raise ValueError
            except ValueError:
                errors.append(
                    _error(row_number, column, value, "Must be a non-negative number")
                )
        for column in CSV_BOOLEAN_COLUMNS:
            value = row.get(column, "").strip()
            if value:
                try:
                    _parse_bool(value)
                except ValueError as error:
                    errors.append(_error(row_number, column, value, str(error)))
        for column in CSV_STRING_COLUMNS:
            value = row.get(column, "").strip()
            if value and re.fullmatch(
                r"(?:[+-]?\d+(?:\.\d+)?[eE][+-]?\d+|[+-]?\d+\.0+)", value
            ):
                errors.append(
                    _error(
                        row_number,
                        column,
                        value,
                        "Value may have lost leading zeros; format this CSV column as text",
                    )
                )
        for column, max_length in CSV_FIELD_MAX_LENGTHS.items():
            value = row.get(column, "")
            if len(value) > max_length:
                errors.append(
                    _error(
                        row_number,
                        column,
                        value,
                        f"Exceeds schema length {max_length}",
                    )
                )

    global_error = any(int(item["rowNumber"]) in {0, 1} for item in errors)
    invalid_rows = {
        int(item["rowNumber"])
        for item in errors
        if int(item["rowNumber"]) >= 2 and item["severity"] == "Error"
    }
    if not global_error:
        for row in rows:
            row_number = int(row["_rowNumber"])
            if row_number in invalid_rows:
                continue
            try:
                payload = map_application_csv_row(row)
                payload_errors = validate_application_fraud_payload(payload)
            except (TypeError, ValueError) as error:
                payload_errors = [str(error)]
            for reason in payload_errors:
                errors.append(_error(row_number, "payload", "", reason))
                invalid_rows.add(row_number)

    valid_rows = (
        []
        if global_error
        else [row for row in rows if int(row["_rowNumber"]) not in invalid_rows]
    )
    return CsvValidationResult(fingerprint, tuple(header), rows, valid_rows, errors)


def _flag(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _rules_from_response(response: SasRuntimeResponse) -> tuple[bool, bool, str]:
    if not isinstance(response.parsed_body, dict):
        return False, False, ""
    message = response.parsed_body.get("message", {})
    sas = message.get("sas", {}) if isinstance(message, dict) else {}
    rules = sas.get("rulefired", []) if isinstance(sas, dict) else []
    rules = rules if isinstance(rules, list) else ([rules] if isinstance(rules, dict) else [])
    fired = [rule for rule in rules if isinstance(rule, dict) and _flag(rule.get("firedFlg"))]
    identifiers = [
        str(
            rule.get("ruleIdentifier")
            or rule.get("ruleName")
            or rule.get("ruleReference")
            or ""
        )
        for rule in fired
    ]
    alert = any(
        _flag(rule.get("alertFlg")) for rule in rules if isinstance(rule, dict)
    ) or summarize_sas_response(response.parsed_body).alert_created
    return bool(fired), alert, ", ".join(item for item in identifiers if item)


def _base_result(row: dict[str, str], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    message = payload.get("message", {}) if payload else {}
    application = message.get("application", {}) if isinstance(message, dict) else {}
    solution = message.get("solution", {}) if isinstance(message, dict) else {}
    system = (
        message.get("sas", {}).get("system", {}) if isinstance(message, dict) else {}
    )
    request = message.get("request", {}) if isinstance(message, dict) else {}
    return {
        "rowNumber": int(row.get("_rowNumber", 0)),
        "applicationIdentifier": application.get("identifier")
        or row.get("applicationIdentifier", ""),
        "customerIdentifier": row.get("customerIdentifier", ""),
        "applicationChannel": application.get("channel")
        or row.get("applicationChannel", ""),
        "solutionChannelType": solution.get("channelType", ""),
        "transactionIdentifier": system.get("transactionIdentifier", ""),
        "messageDtTm": request.get("messageDtTm") or row.get("messageDtTm", ""),
        "httpStatus": None,
        "requestStatus": "",
        "returnType": None,
        "decision": None,
        "firedFlg": False,
        "alertFlg": False,
        "firedRules": "",
        "processingTimeMs": None,
        "errorType": "",
        "errorMessage": "",
        "_request": payload,
        "_rawResponse": "",
        "_parsedResponse": None,
    }


def invalid_batch_results(validation: CsvValidationResult) -> list[dict[str, Any]]:
    """Represent invalid input rows in the result table without sending them."""

    grouped: dict[int, list[str]] = {}
    for item in validation.errors:
        row_number = int(item["rowNumber"])
        if row_number >= 2:
            grouped.setdefault(row_number, []).append(
                f"{item['columnName']}: {item['reason']}"
            )
    rows_by_number = {int(row["_rowNumber"]): row for row in validation.rows}
    results = []
    for row_number, reasons in sorted(grouped.items()):
        source_row = rows_by_number.get(row_number, {"_rowNumber": str(row_number)})
        result = _base_result(source_row)
        result.update(
            requestStatus="Invalid payload",
            errorType="CSV validation error",
            errorMessage=" | ".join(reasons),
        )
        results.append(result)
    return results


def execute_application_batch(
    rows: list[dict[str, str]],
    *,
    endpoint: str,
    timeout_seconds: float,
    verify_tls: bool,
    ca_bundle: str | None,
    delay_seconds: float = 0.5,
    stop_on_error: bool = False,
    sender: Callable[..., SasRuntimeResponse] = send_message,
    sleep: Callable[[float], None] = time.sleep,
    progress: Callable[[int, int, dict[str, str], dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    """Send rows strictly in CSV order. There is intentionally no retry/concurrency."""

    results: list[dict[str, Any]] = []
    total = len(rows)
    for index, row in enumerate(rows, start=1):
        payload: dict[str, Any] | None = None
        result = _base_result(row)
        try:
            payload = map_application_csv_row(row)
            mapping_errors = validate_application_fraud_payload(payload)
            if mapping_errors:
                raise ValueError(" | ".join(mapping_errors))
            result = _base_result(row, payload)
            response = sender(
                endpoint=endpoint,
                payload=payload,
                timeout_seconds=timeout_seconds,
                verify_tls=verify_tls,
                ca_bundle=ca_bundle,
            )
            return_fields = extract_return_fields(response.parsed_body)
            summary = (
                summarize_sas_response(response.parsed_body)
                if response.parsed_body is not None
                else None
            )
            fired, alert, fired_rules = _rules_from_response(response)
            business_error = return_fields.get("returnType") not in {None, 0, "0"}
            request_ok = (
                200 <= response.status_code < 300
                and response.parse_error is None
                and not business_error
            )
            result.update(
                httpStatus=response.status_code,
                requestStatus="Request successful" if request_ok else "Submission failed",
                returnType=return_fields.get("returnType"),
                decision=(summary.outcome_name or summary.outcome) if summary else None,
                firedFlg=fired,
                alertFlg=alert,
                firedRules=fired_rules,
                processingTimeMs=response.elapsed_ms,
                _rawResponse=response.raw_body,
                _parsedResponse=response.parsed_body,
            )
            response_error = str(
                return_fields.get("returnDetails")
                or return_fields.get("returnDesc")
                or f"HTTP {response.status_code}"
            )
            if 400 <= response.status_code < 500:
                result.update(errorType="HTTP 4xx", errorMessage=response_error)
            elif response.status_code >= 500:
                result.update(errorType="HTTP 5xx", errorMessage=response_error)
            elif response.parse_error:
                result.update(
                    errorType="Invalid JSON response", errorMessage=response.parse_error
                )
            elif business_error:
                result.update(
                    errorType="SAS business/runtime error",
                    errorMessage=str(
                        return_fields.get("returnDetails")
                        or return_fields.get("returnDesc")
                        or "SAS returned a non-zero returnType"
                    ),
                )
        except requests.exceptions.SSLError as error:
            result.update(
                requestStatus="Submission failed", errorType="SSL error", errorMessage=str(error)
            )
        except requests.exceptions.Timeout as error:
            result.update(
                requestStatus="Submission failed", errorType="Timeout", errorMessage=str(error)
            )
        except requests.exceptions.ConnectionError as error:
            result.update(
                requestStatus="Submission failed",
                errorType="DNS/connection error",
                errorMessage=str(error),
            )
        except requests.RequestException as error:
            result.update(
                requestStatus="Submission failed",
                errorType="DNS/connection error",
                errorMessage=str(error),
            )
        except (TypeError, ValueError) as error:
            result.update(
                requestStatus="Invalid payload",
                errorType="Payload mapping error",
                errorMessage=str(error),
                _request=payload,
            )

        results.append(result)
        if progress:
            progress(index, total, row, result)
        if stop_on_error and result["requestStatus"] != "Request successful":
            break
        if index < total and delay_seconds > 0:
            sleep(delay_seconds)
    return results


def claim_batch_run(state: MutableMapping[str, Any], fingerprint: str) -> bool:
    """Atomically reserve one file run across Streamlit reruns/double-clicks."""

    if state.get("af_batch_running"):
        return False
    if state.get("af_batch_completed_fingerprint") == fingerprint:
        return False
    state["af_batch_running"] = True
    state["af_batch_active_fingerprint"] = fingerprint
    return True


def finish_batch_run(state: MutableMapping[str, Any], fingerprint: str) -> None:
    state["af_batch_running"] = False
    state["af_batch_completed_fingerprint"] = fingerprint


def reset_batch_for_new_file(state: MutableMapping[str, Any], fingerprint: str) -> None:
    if state.get("af_batch_fingerprint") == fingerprint:
        return
    state["af_batch_fingerprint"] = fingerprint
    state["af_batch_validation"] = None
    state["af_batch_validated_rows"] = []
    state["af_batch_validation_errors"] = []
    state["af_batch_status"] = "idle"
    state["af_batch_progress"] = 0
    state["af_batch_results"] = []
    state["af_batch_details"] = {}
    state["af_batch_running"] = False
    state["af_batch_completed_fingerprint"] = None
    state["af_batch_filter"] = "All results"


def results_to_csv(results: list[dict[str, Any]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output, fieldnames=RESULT_EXPORT_COLUMNS, lineterminator="\n"
    )
    writer.writeheader()
    for result in results:
        request = result.get("_request")
        message = request.get("message", {}) if isinstance(request, dict) else {}
        writer.writerow(
            {
                **{name: result.get(name, "") for name in RESULT_COLUMNS},
                "identificationNumber": (
                    message.get("identification", {}).get("number", "")
                    if isinstance(message, dict)
                    else ""
                ),
                "phoneNumber": (
                    message.get("phone", {}).get("full", "")
                    if isinstance(message, dict)
                    else ""
                ),
                "disbAcctNumber": (
                    message.get("appRisk", {}).get("disbAcctNumber", "")
                    if isinstance(message, dict)
                    else ""
                ),
                "requestJson": (
                    json.dumps(request, ensure_ascii=False, separators=(",", ":"))
                    if request is not None
                    else ""
                ),
                "rawResponse": result.get("_rawResponse", ""),
            }
        )
    return output.getvalue().encode("utf-8-sig")


def payload_contains_null_strings(payload: Any) -> bool:
    """Test helper guarding against the common pandas 'nan'/'None' leak."""

    if isinstance(payload, dict):
        return any(payload_contains_null_strings(value) for value in payload.values())
    if isinstance(payload, list):
        return any(payload_contains_null_strings(value) for value in payload)
    return isinstance(payload, str) and payload.strip().lower() in NULL_TOKENS
