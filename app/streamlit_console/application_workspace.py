"""Operational Streamlit workspace for Application Fraud only."""

from __future__ import annotations

import hashlib
import os
import random
import uuid
from base64 import b64encode
from datetime import datetime, timezone
from typing import Any, MutableMapping

import requests
import streamlit as st
import streamlit.components.v1 as components

try:
    from .alert_log import record_alert
    from .application_batch import (
        application_csv_template,
        claim_batch_run,
        execute_application_batch,
        finish_batch_run,
        invalid_batch_results,
        parse_application_csv,
        reset_batch_for_new_file,
        results_to_csv,
    )
    from .application_config import APPLICATION_CHANNELS
    from .application_demo import DEMO_SPECS, DemoSpec, run_demo_steps
    from .application_json import (
        apply_payload_to_state,
        format_payload,
        merge_form_payload,
        parse_and_validate_payload,
    )
    from .payloads import (
        build_application_fraud_payload,
        validate_application_fraud_payload,
    )
    from .sas_client import SasRuntimeResponse, fetch_runtime_description, send_message
    from .sas_response import (
        ApplicationFiredRule,
        extract_application_fired_rules,
        normalize_application_result,
        summarize_sas_response,
    )
except ImportError:
    from alert_log import record_alert
    from application_batch import (
        application_csv_template,
        claim_batch_run,
        execute_application_batch,
        finish_batch_run,
        invalid_batch_results,
        parse_application_csv,
        reset_batch_for_new_file,
        results_to_csv,
    )
    from application_config import APPLICATION_CHANNELS
    from application_demo import DEMO_SPECS, DemoSpec, run_demo_steps
    from application_json import (
        apply_payload_to_state,
        format_payload,
        merge_form_payload,
        parse_and_validate_payload,
    )
    from payloads import (
        build_application_fraud_payload,
        validate_application_fraud_payload,
    )
    from sas_client import SasRuntimeResponse, fetch_runtime_description, send_message
    from sas_response import (
        ApplicationFiredRule,
        extract_application_fired_rules,
        normalize_application_result,
        summarize_sas_response,
    )


ALERT_TYPE_CODE = "app_fraud_app"
ALERT_ENTITY_TYPE = "sfd_application"


def _new_application_id() -> str:
    return f"APP-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def _new_transaction_id() -> str:
    return f"MSG-{uuid.uuid4().hex[:16].upper()}"


def _random_digits(length: int) -> str:
    return "".join(random.choices("0123456789", k=length))


def _new_applicant_id() -> str:
    return f"APL-DEMO-{uuid.uuid4().hex[:8].upper()}"


def _new_customer_id() -> str:
    return f"CUST-DEMO-{uuid.uuid4().hex[:8].upper()}"


def _new_identification_number() -> str:
    return _random_digits(12)


def _new_phone() -> str:
    return "09" + _random_digits(8)


def _new_device_id() -> str:
    return f"DEV-DEMO-{uuid.uuid4().hex[:8].upper()}"


def _new_disb_account() -> str:
    return _random_digits(14)


def _new_reference_phone() -> str:
    return "09" + _random_digits(8)


def _new_normalized_address() -> str:
    return f"{uuid.uuid4().hex[:6].upper()} DEMO STREET"


def _new_sales_agent() -> str:
    return f"SALES-DEMO-{uuid.uuid4().hex[:6].upper()}"


# Session-state keys that drive SAS Profile keys for the manual form. Kept as a
# single list so the two reset actions and the isolation tests all agree on
# exactly which keys count as "profile-driving" for a manual test identity.
MANUAL_PROFILE_KEYS: tuple[str, ...] = (
    "af_single_applicant_id",
    "af_single_customer_id",
    "af_single_identification_number",
    "af_single_phone",
    "af_single_device_id",
    "af_single_disb_account",
    "af_single_reference_phone",
    "af_single_normalized_address",
    "af_single_sales_agent",
)


def _initialize_state() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    defaults = {
        "af_single_application_id": _new_application_id(),
        "af_single_transaction_id": _new_transaction_id(),
        "af_single_applicant_id": _new_applicant_id(),
        "af_single_customer_id": _new_customer_id(),
        "af_single_identification_number": _new_identification_number(),
        "af_single_phone": _new_phone(),
        "af_single_device_id": _new_device_id(),
        "af_single_disb_account": _new_disb_account(),
        "af_single_reference_phone": _new_reference_phone(),
        "af_single_normalized_address": _new_normalized_address(),
        "af_single_sales_agent": _new_sales_agent(),
        "af_form_application_type": "PERSONAL_LOAN",
        "af_form_application_amount": 50_000_000.0,
        "af_form_currency": "VND",
        "af_form_channel": "MOBILE_APP",
        "af_form_purpose": "PERSONAL_USE",
        "af_form_status": "SUBMITTED",
        "af_form_stage": "UNDER_REVIEW",
        "af_form_event_date": now.date(),
        "af_form_event_time": now.time(),
        "af_form_applicant_name": "Nguyễn Văn Demo",
        "af_form_customer_name": "Nguyễn Văn Demo",
        "af_form_customer_type": "INDIVIDUAL",
        "af_form_country": "VN",
        "af_form_email": "demo.application@example.com",
        "af_form_months_at_location": 24,
        "af_form_employer_name": "Công ty Demo",
        "af_form_employment_status": "EMPLOYED",
        "af_form_monthly_income": 25_000_000.0,
        "af_form_outstanding_debt": 5_000_000.0,
        "af_form_ip_address": "203.0.113.42",
        "af_form_bank_id": "BANK-DEMO",
        "af_form_disb_owner_match": True,
        "af_form_employer_verified": True,
        "af_effective_payload": None,
        "af_form_payload_snapshot": None,
        "af_json_editor_text": "",
        "af_json_validation_errors": [],
        "af_json_applied_notice": False,
        "af_single_sending": False,
        "af_single_last_transaction": None,
        "af_single_result": None,
        "af_batch_fingerprint": None,
        "af_batch_validation": None,
        "af_batch_validated_rows": [],
        "af_batch_validation_errors": [],
        "af_batch_status": "idle",
        "af_batch_progress": 0,
        "af_batch_results": [],
        "af_batch_details": {},
        "af_batch_running": False,
        "af_batch_completed_fingerprint": None,
        "af_batch_filter": "All results",
        "af_pending_result_dialog": None,
        "af_demo_pending_dialog": None,
        "af_demo1_result": None,
        "af_demo2_result": None,
        "af_demo3_result": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def apply_new_application_same_customer(state: MutableMapping[str, Any]) -> None:
    """Action A: a new application/transaction from the SAME identity.

    Keeps every profile-driving key (customer, applicant, CCCD, phone, device,
    disbursement account, reference phone, address, sales agent) untouched —
    this intentionally tests another application from the same identity, so it
    may legitimately hit the same SAS Profile history.
    """

    state["af_single_application_id"] = _new_application_id()
    state["af_single_transaction_id"] = _new_transaction_id()
    state["af_single_last_transaction"] = None
    state["af_single_result"] = None


def apply_fresh_test_dataset(state: MutableMapping[str, Any]) -> None:
    """Action B: fresh values for every profile-driving key.

    This is the isolated smoke-test reset — it does not delete any SAS
    Profile, it only stops reusing keys that carry prior history, so a
    'normal / no-alert' demo application is unlikely to inherit an old
    Redis profile by accident.
    """

    state["af_single_application_id"] = _new_application_id()
    state["af_single_transaction_id"] = _new_transaction_id()
    state["af_single_applicant_id"] = _new_applicant_id()
    state["af_single_customer_id"] = _new_customer_id()
    state["af_single_identification_number"] = _new_identification_number()
    state["af_single_phone"] = _new_phone()
    state["af_single_device_id"] = _new_device_id()
    state["af_single_disb_account"] = _new_disb_account()
    state["af_single_reference_phone"] = _new_reference_phone()
    state["af_single_normalized_address"] = _new_normalized_address()
    state["af_single_sales_agent"] = _new_sales_agent()
    state["af_single_last_transaction"] = None
    state["af_single_result"] = None
    state["af_effective_payload"] = None
    state["af_form_payload_snapshot"] = None
    state["af_json_editor_text"] = ""
    state["af_json_validation_errors"] = []


def _render_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #f6f8fb; }
        [data-testid="stSidebarNav"] { display: none; }
        [data-testid="stHeader"] { background: rgba(246,248,251,.92); }
        [data-testid="stSidebar"] { border-right: 1px solid #dce3ec; }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff;
            border-color: #dce3ec;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(15, 42, 68, .04);
        }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e0e7ef;
            border-radius: 9px;
            padding: .8rem 1rem;
        }
        .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
            background: #0b4f84;
            border-color: #0b4f84;
        }
        .af-console-header {
            background: linear-gradient(115deg, #082b4a 0%, #0b4f84 100%);
            border-radius: 12px;
            padding: 20px 24px;
            margin: 0 0 18px 0;
            color: #ffffff;
        }
        .af-console-header h2 { color: #ffffff; font-size: 1.25rem; margin: 0; }
        .af-console-header p { color: #d7e7f5; margin: 5px 0 0 0; }
        .af-eyebrow { color:#9cc7e8; font-size:.72rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; }
        .af-section-title {
            color: #0b3558;
            font-size: 1rem;
            font-weight: 700;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 6px;
            margin: 8px 0 14px 0;
        }
        .af-contract-note {
            background: #f7f9fc;
            border: 1px solid #d8dee8;
            border-radius: 3px;
            color: #374151;
            padding: 10px 12px;
        }
        .af-status-alert { background:#fff7ed;border:1px solid #fed7aa;border-left:5px solid #d97706;border-radius:10px;padding:18px 20px; }
        .af-status-clear { background:#f0fdf4;border:1px solid #bbf7d0;border-left:5px solid #15803d;border-radius:10px;padding:18px 20px; }
        .af-status-error { background:#fef2f2;border:1px solid #fecaca;border-left:5px solid #b91c1c;border-radius:10px;padding:18px 20px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _section(title: str) -> None:
    st.markdown(f'<div class="af-section-title">{title}</div>', unsafe_allow_html=True)


def _utc_string(selected_date: Any, selected_time: Any) -> str:
    return (
        datetime.combine(selected_date, selected_time, tzinfo=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _fired_rules_table_rows(
    fired_rules: list[ApplicationFiredRule],
) -> list[dict[str, Any]]:
    # Every raw SAS field a Decision Rule can carry is kept as its own column —
    # ruleIdentifier and referenceIdentifier are never collapsed into one field.
    return [
        {
            "Rule": rule.display_name,
            "Reason": rule.reason or "—",
            "Alert": "Yes" if rule.alert else "No",
            "SAS outcome entity": rule.entity or "—",
            "SAS outcome entity type": rule.entity_type or "—",
            "Rule identifier": rule.rule_identifier or "—",
            "Reference": rule.rule_reference or "—",
        }
        for rule in fired_rules
    ]


def _render_fired_rules_table(fired_rules: list[ApplicationFiredRule]) -> None:
    if not fired_rules:
        st.info("No Decision Rule fired.")
        return
    st.dataframe(
        _fired_rules_table_rows(fired_rules), use_container_width=True, hide_index=True
    )


def _render_alerted_entities_section(alerted_entities: list[dict[str, Any]]) -> None:
    if not alerted_entities:
        return
    _section("Alerted entities")
    st.caption(
        "Technical field: outcomeEntityType may differ from the entity type configured "
        "in Alert Triage."
    )
    st.dataframe(
        [
            {
                "SAS outcome entity": item.get("outcomeEntity", ""),
                "SAS outcome entity type": item.get("outcomeEntityType", ""),
            }
            for item in alerted_entities
            if isinstance(item, dict)
        ],
        use_container_width=True,
        hide_index=True,
    )


def _rule_matches_target(rule: ApplicationFiredRule, target_rule: str) -> bool:
    candidates = (rule.rule_name, rule.rule_reference, rule.display_name)
    return any(
        isinstance(candidate, str) and candidate.strip() == target_rule
        for candidate in candidates
    )


@st.dialog("Kết quả sàng lọc")
def _show_application_result_dialog(entry: dict[str, Any]) -> None:
    st.markdown("## Hồ sơ cần xem xét")

    fired_rules = entry.get("fired_rules") or []
    if fired_rules:
        for rule in fired_rules:
            st.markdown(f"**Quy tắc phát hiện:** `{rule.get('name', '')}`")
            if rule.get("reason"):
                st.markdown(f"**Lý do cảnh báo:** {rule['reason']}")
    else:
        st.caption("SAS không trả về tên quy tắc cụ thể cho cảnh báo này.")

    alert_id = entry.get("alert_id")
    st.markdown(
        f"**Alert ID:** `{alert_id}`"
        if alert_id
        else "**Alert ID:** Không được trả về trong runtime response hiện tại"
    )
    st.caption(f"Application ID: {entry.get('application_identifier', '')}")
    st.caption(f"Customer ID: {entry.get('customer_identifier', '')}")
    st.markdown("**Trạng thái:** Đã tạo cảnh báo")

    if st.button(
        "Đóng", type="primary", use_container_width=True, key="af_manual_dialog_close"
    ):
        st.session_state["af_pending_result_dialog"] = None
        st.rerun()


@st.dialog("Alert Demo Result")
def _show_quick_demo_result_dialog(entry: dict[str, Any]) -> None:
    """Quick Demo's own popup — independent of af_pending_result_dialog.

    Only the caller triggers this for the final (trigger) step of a demo
    sequence; seed steps never open a popup (see _render_quick_demos).
    """

    st.markdown("## :material/warning: Application Alert")
    st.markdown(f"**Target rule:** `{entry.get('target_rule', '')}`")
    st.markdown(f"**Actual fired rule:** `{entry.get('actual_rule_name', '')}`")
    if entry.get("reason"):
        st.markdown(f"**Reason:** {entry['reason']}")
    st.caption(f"Application: {entry.get('application_identifier', '')}")
    st.caption(f"Customer: {entry.get('customer_identifier', '')}")
    if entry.get("alert_id"):
        st.code(str(entry["alert_id"]), language=None)
    else:
        st.caption("Alert ID không được trả về trong runtime response hiện tại.")
    st.markdown("**Alert:** Created")

    if st.button(
        "Close", type="primary", use_container_width=True, key="af_demo_dialog_close"
    ):
        st.session_state["af_demo_pending_dialog"] = None
        st.rerun()


def _record_alert_if_created(
    payload: dict[str, Any], response: SasRuntimeResponse, *, show_dialog: bool = True
) -> None:
    if response.parsed_body is None:
        return
    normalized = normalize_application_result(
        response.parsed_body,
        payload=payload,
        http_status=response.status_code,
        elapsed_ms=response.elapsed_ms,
        parse_error=response.parse_error,
    )
    if not normalized.alert_created:
        return

    fired_rules = normalized.fired_rules
    message = payload["message"]
    record_alert(
        {
            "recorded_at": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "fraud_domain": "Application Fraud",
            "schema_name": "Application Fraud",
            "alert_type": ALERT_TYPE_CODE,
            "application_identifier": message["application"]["identifier"],
            "customer_identifier": message["customer"]["identifier"],
            "customer_name": message.get("customer", {}).get("surname"),
            "channel": message.get("application", {}).get("channel"),
            "transaction_identifier": normalized.transaction_id,
            "message_identifier": normalized.message_id,
            "alert_id": normalized.alert_id,
            "alert_reason": normalized.alert_reason,
            "evidence": normalized.evidence,
            "decision": normalized.decision,
            "alert_status": "Alert created",
            "actual_alert": normalized.alert_created,
            "fired_rules": [rule.display_name for rule in fired_rules],
            "fired_rule_identifiers": [
                rule.rule_identifier or rule.display_name for rule in fired_rules
            ],
            "http_status": response.status_code,
            "fired_rule_details": [rule.raw for rule in fired_rules],
            "outcome_name": normalized.outcome_name,
            "alerted_entities": normalized.alerted_entities,
            "rule_fired": bool(fired_rules),
            "raw_response": response.parsed_body,
        }
    )
    if show_dialog:
        st.session_state["af_pending_result_dialog"] = {
            "outcome_name": normalized.outcome_name,
            "alert_id": normalized.alert_id,
            "application_identifier": message["application"]["identifier"],
            "customer_identifier": message["customer"]["identifier"],
            "fired_rules": [
                {"name": rule.display_name, "reason": rule.reason}
                for rule in fired_rules
            ],
        }


def _manual_result_identity(result: dict[str, Any]) -> dict[str, Any]:
    """Identity that PRODUCED this result, read from the sent payload only.

    Never reads current (possibly since-edited) form widgets — the form can be
    changed after sending without retroactively relabeling an old result.
    """

    payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
    message = payload.get("message", {}) if isinstance(payload, dict) else {}
    application = message.get("application", {}) if isinstance(message, dict) else {}
    customer = message.get("customer", {}) if isinstance(message, dict) else {}
    system = (
        message.get("sas", {}).get("system", {})
        if isinstance(message.get("sas"), dict)
        else {}
    )
    return {
        "application_identifier": application.get("identifier", "") or "",
        "transaction_identifier": system.get("transactionIdentifier", "") or "",
        "customer_identifier": customer.get("identifier", "") or "",
        "sent_at": result.get("sent_at", "") or "",
    }


def _display_outcome(outcome_raw: Any) -> str:
    """Never invent Review/Decline — a missing or 'Unknown' outcome stays honest."""

    if outcome_raw is None:
        return "No explicit outcome"
    text = str(outcome_raw).strip()
    if not text or text.lower() == "unknown":
        return "No explicit outcome"
    return text


def _render_single_result(result: dict[str, Any]) -> None:
    response: SasRuntimeResponse = result["response"]
    payload: dict[str, Any] = result["payload"]
    identity = _manual_result_identity(result)
    normalized = normalize_application_result(
        response.parsed_body,
        payload=payload,
        http_status=response.status_code,
        elapsed_ms=response.elapsed_ms,
        parse_error=response.parse_error,
    )

    _section("Kết quả sàng lọc")
    if not normalized.request_ok:
        st.markdown(
            '<div class="af-status-error"><h3>Không thể hoàn tất sàng lọc gian lận</h3>'
            "<p>Dịch vụ chưa trả về một kết quả hợp lệ. Xem Chi tiết kỹ thuật để chẩn đoán.</p></div>",
            unsafe_allow_html=True,
        )
    elif normalized.alert_created:
        st.markdown(
            '<div class="af-status-alert"><h3>Hồ sơ cần xem xét</h3>'
            "<p>SAS Fraud Decisioning đã tạo cảnh báo cho hồ sơ này.</p></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="af-status-clear"><h3>Không phát hiện dấu hiệu bất thường</h3>'
            "<p>Không có quy tắc gian lận nào khớp với hồ sơ và lịch sử hiện có.</p></div>",
            unsafe_allow_html=True,
        )

    columns = st.columns(4)
    columns[0].metric("Application ID", identity["application_identifier"] or "—")
    columns[1].metric("Customer ID", identity["customer_identifier"] or "—")
    columns[2].metric("Quyết định", _display_outcome(normalized.decision))
    columns[3].metric("Cảnh báo", "Đã tạo" if normalized.alert_created else "Không")

    if normalized.alert_created:
        st.markdown("#### Alert ID")
        if normalized.alert_id:
            st.code(normalized.alert_id, language=None)
        else:
            st.warning("Alert ID không được trả về trong runtime response hiện tại.")
        st.markdown("#### Vì sao hồ sơ bị cảnh báo?")
        if normalized.alert_reason:
            st.write(normalized.alert_reason)
        elif normalized.fired_rules:
            st.caption("SAS trả về quy tắc nhưng không kèm alertReason/ruleReason.")
        _render_fired_rules_table(normalized.fired_rules)
        if normalized.evidence:
            st.markdown("#### Bằng chứng / Dấu hiệu rủi ro")
            st.dataframe(normalized.evidence, use_container_width=True, hide_index=True)

    with st.expander("Chi tiết kỹ thuật", expanded=False):
        tech_columns = st.columns(4)
        tech_columns[0].metric("HTTP status", response.status_code)
        tech_columns[1].metric("Round trip", f"{response.elapsed_ms} ms")
        tech_columns[2].metric("returnType", normalized.return_type)
        tech_columns[3].metric("Transaction ID", normalized.transaction_id or "—")
        st.caption(
            f"Message ID: {normalized.message_id or '—'} · "
            f"Decision reference: {normalized.decision_reference or '—'} · "
            f"Processed at: {identity['sent_at']}"
        )
        request_tab, response_tab, parsed_tab = st.tabs(
            ["Request JSON", "Raw SAS response", "Parsed response"]
        )
        with request_tab:
            st.json(payload, expanded=False)
        with response_tab:
            st.code(response.raw_body, language="text", wrap_lines=True)
        with parsed_tab:
            st.json(response.parsed_body, expanded=False)


def _form_values_from_state(state: MutableMapping[str, Any]) -> dict[str, Any]:
    return {
        "message_datetime": _utc_string(
            state["af_form_event_date"], state["af_form_event_time"]
        ),
        "application_identifier": state["af_single_application_id"],
        "transaction_identifier": state["af_single_transaction_id"],
        "application_type": state["af_form_application_type"],
        "application_amount": state["af_form_application_amount"],
        "currency_code": state["af_form_currency"],
        "application_channel": state["af_form_channel"],
        "application_purpose": state["af_form_purpose"],
        "application_status": state["af_form_status"],
        "application_stage": state["af_form_stage"],
        "applicant_identifier": state["af_single_applicant_id"],
        "applicant_name": state["af_form_applicant_name"],
        "monthly_regular_income": state["af_form_monthly_income"],
        "outstanding_debt": state["af_form_outstanding_debt"],
        "employer_name": state["af_form_employer_name"],
        "employment_status": state["af_form_employment_status"],
        "customer_identifier": state["af_single_customer_id"],
        "customer_name": state["af_form_customer_name"],
        "customer_type": state["af_form_customer_type"],
        "address_country_code": str(state["af_form_country"]).upper(),
        "identification_number": state["af_single_identification_number"],
        "email": state["af_form_email"],
        "phone": state["af_single_phone"],
        "months_at_location": state["af_form_months_at_location"],
        "device_identifier": state["af_single_device_id"],
        "device_ip_address": state["af_form_ip_address"],
        "app_risk": {
            "bankId": state["af_form_bank_id"],
            "salesAgentIdentifier": state["af_single_sales_agent"],
            "disbAcctNumber": state["af_single_disb_account"],
            "referencePhone": state["af_single_reference_phone"],
            "normalizedAddress": state["af_single_normalized_address"],
            "disbAcctOwnerMatchInd": int(state["af_form_disb_owner_match"]),
            "employerUnverifiedInd": int(not state["af_form_employer_verified"]),
        },
    }


def _apply_json_editor() -> None:
    payload, errors = parse_and_validate_payload(
        st.session_state.get("af_json_editor_text", "")
    )
    st.session_state["af_json_validation_errors"] = errors
    st.session_state["af_json_applied_notice"] = False
    if payload is None:
        return
    apply_payload_to_state(payload, st.session_state)
    st.session_state["af_effective_payload"] = payload
    st.session_state["af_form_payload_snapshot"] = payload
    st.session_state["af_json_editor_text"] = format_payload(payload)
    st.session_state["af_json_applied_notice"] = True


def _restore_json_from_form() -> None:
    payload = build_application_fraud_payload(_form_values_from_state(st.session_state))
    st.session_state["af_effective_payload"] = payload
    st.session_state["af_form_payload_snapshot"] = payload
    st.session_state["af_json_editor_text"] = format_payload(payload)
    st.session_state["af_json_validation_errors"] = []
    st.session_state["af_json_applied_notice"] = False


def _copy_json_control(payload_text: str) -> None:
    encoded = b64encode(payload_text.encode("utf-8")).decode("ascii")
    components.html(
        f"""
        <button id="copy" style="border:1px solid #b8c5d3;border-radius:7px;background:#fff;
        color:#0b3558;padding:8px 14px;font:600 14px system-ui;cursor:pointer">Copy JSON</button>
        <span id="status" style="color:#4b6478;font:13px system-ui;margin-left:8px"></span>
        <script>
        const text = new TextDecoder().decode(Uint8Array.from(atob('{encoded}'), c => c.charCodeAt(0)));
        document.getElementById('copy').onclick = async () => {{
          try {{ await navigator.clipboard.writeText(text); document.getElementById('status').innerText='Copied'; }}
          catch (_) {{ document.getElementById('status').innerText='Use the copy icon in the JSON block'; }}
        }};
        </script>
        """,
        height=42,
    )


def _render_single(
    *, endpoint: str, timeout_seconds: float, verify_tls: bool, ca_bundle: str | None
) -> None:
    # Rendered only inside the manual tab — Quick Demo has its own independent
    # af_demo_pending_dialog/_show_quick_demo_result_dialog (see _render_quick_demos).
    pending_dialog = st.session_state.get("af_pending_result_dialog")
    if pending_dialog:
        _show_application_result_dialog(pending_dialog)

    channel_codes = list(APPLICATION_CHANNELS)

    _section("Chuẩn bị hồ sơ")
    reset_col1, reset_col2 = st.columns(2)
    if reset_col1.button(
        "Hồ sơ mới — Giữ khách hàng",
        key="af_reset_same_customer",
        use_container_width=True,
        help=(
            "Generate a new application identifier and transaction identifier while "
            "keeping all customer and Profile keys unchanged."
        ),
    ):
        apply_new_application_same_customer(st.session_state)
        st.rerun()
    if reset_col2.button(
        "Tạo bộ dữ liệu demo mới",
        key="af_reset_fresh_dataset",
        use_container_width=True,
        help=(
            "Generate new values for every Profile key before a normal no-alert test. "
            "This does not delete any Profile stored by SAS."
        ),
    ):
        apply_fresh_test_dataset(st.session_state)
        st.rerun()

    with st.container(border=True):
        _section("Thông tin hồ sơ")
        first, second = st.columns(2)
        first.text_input("Application ID", key="af_single_application_id")
        second.selectbox(
            "Sản phẩm vay",
            ["PERSONAL_LOAN", "HOME_LOAN", "AUTO_LOAN"],
            key="af_form_application_type",
        )
        first.number_input(
            "Số tiền đề nghị",
            min_value=0.0,
            step=1_000_000.0,
            key="af_form_application_amount",
        )
        second.selectbox("Loại tiền", ["VND", "USD"], key="af_form_currency")
        first.selectbox(
            "Mục đích vay",
            ["PERSONAL_USE", "HOME_RENOVATION", "VEHICLE_PURCHASE"],
            key="af_form_purpose",
        )
        second.selectbox(
            "Trạng thái hồ sơ",
            ["SUBMITTED", "PENDING", "APPROVED"],
            key="af_form_status",
        )
        first.selectbox(
            "Giai đoạn xử lý",
            ["UNDER_REVIEW", "DOCUMENT_CHECK", "DECISION"],
            key="af_form_stage",
        )
        second.date_input("Ngày gửi", key="af_form_event_date")
        first.time_input("Giờ gửi (UTC)", key="af_form_event_time")
        second.selectbox(
            "Kênh tiếp nhận",
            channel_codes,
            format_func=lambda code: APPLICATION_CHANNELS[code]["label"],
            key="af_form_channel",
        )
        channel = st.session_state["af_form_channel"]
        if channel == "BRANCH":
            st.caption("Hồ sơ được nhân viên tại quầy nhập trực tiếp.")
        elif channel in {"MOBILE_APP", "WEB"}:
            st.caption(
                "Hồ sơ khởi tạo trên kênh số và đang được nhân viên ngân hàng xử lý."
            )
        else:
            st.caption("Nguồn tiếp nhận được giữ nguyên trong thông điệp gửi SAS.")

        _section("Thông tin khách hàng")
        first, second = st.columns(2)
        first.text_input("Applicant ID", key="af_single_applicant_id")
        second.text_input("Họ và tên người vay", key="af_form_applicant_name")
        first.text_input("Customer ID", key="af_single_customer_id")
        second.text_input("Tên khách hàng", key="af_form_customer_name")
        first.selectbox(
            "Loại khách hàng", ["INDIVIDUAL", "BUSINESS"], key="af_form_customer_type"
        )
        second.text_input("Quốc gia", max_chars=3, key="af_form_country")
        first, second = st.columns(2)
        first.text_input("Số giấy tờ định danh", key="af_single_identification_number")
        second.text_input("Email", key="af_form_email")
        first.text_input("Số điện thoại", key="af_single_phone")
        second.number_input(
            "Số tháng tại địa chỉ hiện tại",
            min_value=0,
            step=1,
            key="af_form_months_at_location",
        )

        _section("Nghề nghiệp & tài chính")
        first, second = st.columns(2)
        first.text_input("Đơn vị công tác", key="af_form_employer_name")
        second.selectbox(
            "Tình trạng việc làm",
            ["EMPLOYED", "SELF_EMPLOYED", "UNEMPLOYED"],
            key="af_form_employment_status",
        )
        first.number_input(
            "Thu nhập thường xuyên hàng tháng",
            min_value=0.0,
            step=1_000_000.0,
            key="af_form_monthly_income",
        )
        second.number_input(
            "Dư nợ hiện tại",
            min_value=0.0,
            step=1_000_000.0,
            key="af_form_outstanding_debt",
        )

        _section("Giải ngân & thông tin tham chiếu")
        first, second = st.columns(2)
        first.text_input("Mã ngân hàng / tổ chức", key="af_form_bank_id")
        second.text_input("Sales Agent ID", key="af_single_sales_agent")
        first.text_input("Tài khoản giải ngân", key="af_single_disb_account")
        second.text_input("Điện thoại tham chiếu", key="af_single_reference_phone")
        st.text_input("Địa chỉ chuẩn hóa", key="af_single_normalized_address")
        first.checkbox(
            "Chủ tài khoản giải ngân trùng với người vay",
            key="af_form_disb_owner_match",
        )
        second.checkbox(
            "Đơn vị công tác đã được xác minh", key="af_form_employer_verified"
        )

        with st.expander("Thiết bị & thông tin tiếp nhận", expanded=False):
            first, second = st.columns(2)
            first.text_input("Device ID", key="af_single_device_id")
            second.text_input("IP Address", key="af_form_ip_address")
            st.caption(
                "Phần này hữu ích cho hồ sơ phát sinh từ Mobile App hoặc Website."
            )

    values = _form_values_from_state(st.session_state)
    try:
        form_payload = build_application_fraud_payload(values)
    except ValueError as error:
        form_payload = None
        validation_errors = [str(error)]
    else:
        previous = st.session_state.get("af_form_payload_snapshot")
        effective = st.session_state.get("af_effective_payload")
        if not isinstance(previous, dict) or not isinstance(effective, dict):
            effective = form_payload
        else:
            effective = merge_form_payload(effective, previous, form_payload)
        if effective != st.session_state.get("af_effective_payload"):
            st.session_state["af_json_editor_text"] = format_payload(effective)
        st.session_state["af_effective_payload"] = effective
        st.session_state["af_form_payload_snapshot"] = form_payload
        if not st.session_state.get("af_json_editor_text"):
            st.session_state["af_json_editor_text"] = format_payload(effective)
        validation_errors = validate_application_fraud_payload(effective)

    with st.expander("Message JSON · Xem / chỉnh sửa request payload", expanded=False):
        st.caption(
            "Payload hiệu lực bên dưới chính là payload sẽ gửi. Thay đổi JSON phải được "
            "Validate & Apply trước khi nộp hồ sơ."
        )
        edit_json = st.toggle("Edit JSON", value=False, key="af_json_edit_enabled")
        st.text_area(
            "Request JSON",
            key="af_json_editor_text",
            height=430,
            disabled=not edit_json,
            label_visibility="collapsed",
        )
        _copy_json_control(st.session_state["af_json_editor_text"])
        apply_col, restore_col = st.columns(2)
        apply_col.button(
            "Validate & Apply",
            on_click=_apply_json_editor,
            disabled=not edit_json,
            use_container_width=True,
        )
        restore_col.button(
            "Restore / Rebuild from Form",
            on_click=_restore_json_from_form,
            help="Tạo lại payload từ form và loại bỏ các trường chỉ có trong JSON.",
            use_container_width=True,
        )
        if st.session_state.get("af_json_applied_notice"):
            st.success("JSON hợp lệ và đã trở thành payload hiệu lực.")
        for error in st.session_state.get("af_json_validation_errors", []):
            st.error(error)

    for error in validation_errors:
        st.error(error)

    effective_payload = st.session_state.get("af_effective_payload")
    editor_dirty = isinstance(effective_payload, dict) and st.session_state.get(
        "af_json_editor_text"
    ) != format_payload(effective_payload)
    if editor_dirty:
        st.warning(
            "JSON đang có thay đổi chưa áp dụng. Hãy chọn Validate & Apply trước khi gửi."
        )

    submitted = st.button(
        "Nộp hồ sơ & chạy sàng lọc gian lận",
        type="primary",
        use_container_width=True,
        disabled=bool(validation_errors) or editor_dirty or form_payload is None,
    )

    if submitted:
        transaction_id = st.session_state["af_single_transaction_id"]
        if st.session_state["af_single_sending"] or (
            st.session_state["af_single_last_transaction"] == transaction_id
        ):
            st.warning(
                "This request was already submitted; reruns will not submit it again."
            )
        elif validation_errors or not isinstance(effective_payload, dict):
            st.error("Hồ sơ chứa thông tin không hợp lệ; chưa có request nào được gửi.")
        else:
            st.session_state["af_single_sending"] = True
            st.session_state["af_single_result"] = None

            try:
                with st.status("Đang xử lý hồ sơ", expanded=True) as status:
                    st.write("Đang xác thực thông tin hồ sơ")
                    st.write("Đang gửi tới SAS Fraud Decisioning")
                    response = send_message(
                        endpoint=endpoint,
                        payload=effective_payload,
                        timeout_seconds=timeout_seconds,
                        verify_tls=verify_tls,
                        ca_bundle=ca_bundle,
                    )
                    st.write("Đã nhận quyết định")
                    status.update(
                        label="Hoàn tất sàng lọc", state="complete", expanded=False
                    )
                st.session_state["af_single_result"] = {
                    "payload": effective_payload,
                    "response": response,
                    "sent_at": datetime.now(timezone.utc)
                    .isoformat(timespec="seconds")
                    .replace("+00:00", "Z"),
                }
                if 200 <= response.status_code < 300:
                    st.session_state["af_single_last_transaction"] = transaction_id
                else:
                    # HTTP 4xx/5xx must remain retryable.
                    st.session_state["af_single_last_transaction"] = None

                _record_alert_if_created(effective_payload, response)
                if st.session_state.get("af_pending_result_dialog"):
                    # Setting session_state alone does not reopen a @st.dialog —
                    # it only takes effect on the NEXT script run, so force one.
                    st.rerun()
            except requests.exceptions.SSLError:
                st.session_state["af_single_last_transaction"] = None
                st.error(
                    "Không thể hoàn tất sàng lọc gian lận. Kiểm tra kết nối TLS trong Chi tiết kỹ thuật."
                )
            except requests.exceptions.Timeout:
                st.session_state["af_single_last_transaction"] = None
                st.error("Dịch vụ gian lận không phản hồi trong thời gian cho phép.")
            except requests.exceptions.ConnectionError:
                st.session_state["af_single_last_transaction"] = None
                st.error("Dịch vụ gian lận hiện không khả dụng.")
            except (requests.RequestException, ValueError):
                st.session_state["af_single_last_transaction"] = None
                st.error("Không thể hoàn tất sàng lọc gian lận.")
            finally:
                st.session_state["af_single_sending"] = False

    result = st.session_state.get("af_single_result")
    if result:
        _render_single_result(result)


def _filtered_results(
    results: list[dict[str, Any]], selected: str
) -> list[dict[str, Any]]:
    if selected == "Alerts":
        return [result for result in results if result.get("alertFlg")]
    if selected == "No alerts":
        return [
            result
            for result in results
            if result.get("requestStatus") == "Request successful"
            and not result.get("alertFlg")
        ]
    if selected == "Rules fired":
        return [result for result in results if result.get("firedFlg")]
    if selected == "Failed submissions":
        return [
            result
            for result in results
            if result.get("requestStatus") == "Submission failed"
        ]
    if selected == "Invalid rows":
        return [
            result
            for result in results
            if result.get("requestStatus") == "Invalid payload"
        ]
    return results


def _render_batch_results(results: list[dict[str, Any]]) -> None:
    _section("Bước 5 · Kết quả xử lý")
    success = sum(item.get("requestStatus") == "Request successful" for item in results)
    failed = sum(item.get("requestStatus") == "Submission failed" for item in results)
    alert = sum(bool(item.get("alertFlg")) for item in results)
    no_alert = sum(
        item.get("requestStatus") == "Request successful" and not item.get("alertFlg")
        for item in results
    )
    columns = st.columns(4)
    columns[0].metric("Thành công", success)
    columns[1].metric("Thất bại", failed)
    columns[2].metric("Có cảnh báo", alert)
    columns[3].metric("Không cảnh báo", no_alert)

    selected_filter = st.selectbox(
        "Result filter",
        [
            "All results",
            "Alerts",
            "No alerts",
            "Rules fired",
            "Failed submissions",
            "Invalid rows",
        ],
        key="af_batch_filter",
    )
    filtered = _filtered_results(results, selected_filter)
    business_rows = [
        {
            "Application ID": row.get("applicationIdentifier"),
            "Customer ID": row.get("customerIdentifier"),
            "Kênh": row.get("applicationChannel"),
            "Quyết định": row.get("decision"),
            "Quy tắc phát hiện": row.get("firedRules") or "—",
            "Cảnh báo": "Có" if row.get("alertFlg") else "Không",
            "Alert ID": row.get("alertId") or "Không được trả về",
            "Thời gian (ms)": row.get("processingTimeMs"),
            "Trạng thái": row.get("requestStatus"),
        }
        for row in filtered
    ]
    st.dataframe(
        business_rows,
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Tải kết quả CSV",
        data=results_to_csv(results),
        file_name="application_fraud_batch_results.csv",
        mime="text/csv",
        key="af_download_results",
        use_container_width=True,
    )
    if filtered:
        labels = [
            f"Row {item['rowNumber']} — {item['applicationIdentifier']}"
            for item in filtered
        ]
        selected_label = st.selectbox(
            "Chi tiết từng hồ sơ", labels, key="af_result_detail"
        )
        detail = filtered[labels.index(selected_label)]
        with st.expander("Chi tiết kỹ thuật", expanded=False):
            st.markdown("**Request JSON**")
            if detail.get("_request") is None:
                st.info("The invalid row was not mapped or submitted.")
            else:
                st.json(detail["_request"], expanded=False)
            st.markdown("**SAS response**")
            if detail.get("_parsedResponse") is not None:
                st.json(detail["_parsedResponse"], expanded=False)
            elif detail.get("_rawResponse"):
                st.code(detail["_rawResponse"], language="text", wrap_lines=True)
            else:
                st.info(
                    detail.get("errorMessage") or "No runtime response is available."
                )


def _render_batch(
    *, endpoint: str, timeout_seconds: float, verify_tls: bool, ca_bundle: str | None
) -> None:
    _section("Bước 1 · Tải biểu mẫu")
    st.download_button(
        "Tải CSV Template",
        data=application_csv_template(),
        file_name="application_fraud_template.csv",
        mime="text/csv",
        key="af_download_template",
        use_container_width=True,
    )
    _section("Bước 2 · Tải tệp hồ sơ")
    uploaded = st.file_uploader(
        "Chọn tệp CSV", type=["csv"], key="af_csv_upload", accept_multiple_files=False
    )
    if uploaded is None:
        st.info(
            "Tải biểu mẫu, nhập dữ liệu hồ sơ và tải lên để kiểm tra trước khi gửi."
        )
        return

    data = uploaded.getvalue()
    fingerprint = hashlib.sha256(data).hexdigest()
    reset_batch_for_new_file(st.session_state, fingerprint)
    validation = st.session_state.get("af_batch_validation")
    if validation is None:
        validation = parse_application_csv(data)
        st.session_state["af_batch_validation"] = validation
        st.session_state["af_batch_validated_rows"] = validation.valid_rows
        st.session_state["af_batch_validation_errors"] = validation.errors

    _section("Bước 3 · Kiểm tra dữ liệu")
    validation_metrics = st.columns(3)
    validation_metrics[0].metric("Tổng số dòng", len(validation.rows))
    validation_metrics[1].metric("Hợp lệ", len(validation.valid_rows))
    validation_metrics[2].metric("Không hợp lệ", len(validation.errors))
    if validation.rows:
        preview_columns = [column for column in validation.columns if column]
        st.dataframe(
            [
                {column: row.get(column, "") for column in preview_columns}
                for row in validation.rows[:100]
            ],
            use_container_width=True,
            hide_index=True,
        )
    if validation.errors:
        st.dataframe(validation.errors, use_container_width=True, hide_index=True)
    else:
        st.success("Tất cả hồ sơ đều hợp lệ.")

    _section("Bước 4 · Gửi hồ sơ hợp lệ")
    first, second, third = st.columns(3)
    delay_seconds = first.number_input(
        "Khoảng nghỉ giữa request (giây)",
        min_value=0.0,
        max_value=60.0,
        value=0.5,
        step=0.1,
        key="af_batch_delay",
    )
    batch_timeout = second.number_input(
        "Timeout mỗi request (giây)",
        min_value=1.0,
        max_value=300.0,
        value=float(timeout_seconds),
        step=1.0,
        key="af_batch_timeout",
    )
    stop_mode = third.selectbox(
        "Khi có lỗi", ["Continue", "Stop batch"], key="af_batch_stop_mode"
    )
    confirmed = st.checkbox(
        "Tôi đã kiểm tra dữ liệu; chỉ gửi các dòng hợp lệ.", key="af_batch_confirm"
    )
    already_completed = (
        st.session_state.get("af_batch_completed_fingerprint") == fingerprint
    )
    run_clicked = st.button(
        "Gửi các hồ sơ hợp lệ",
        type="primary",
        key="af_run_batch",
        disabled=(
            not validation.valid_rows
            or not confirmed
            or st.session_state.get("af_batch_running", False)
            or already_completed
        ),
        use_container_width=True,
    )
    if already_completed:
        st.caption(
            "This file has already run in the current session. Upload a different file to create a new batch."
        )

    if run_clicked:
        if not claim_batch_run(st.session_state, fingerprint):
            st.warning(
                "The batch is running or has completed; duplicate submission was blocked."
            )
        else:
            st.session_state["af_batch_status"] = "running"
            st.session_state["af_batch_progress"] = 0
            progress_bar = st.progress(0.0)
            current_text = st.empty()
            metric_columns = st.columns(4)
            counters = {"success": 0, "failed": 0, "alert": 0, "no_alert": 0}

            def update_progress(
                current: int,
                total: int,
                row: dict[str, str],
                result: dict[str, Any],
            ) -> None:
                progress_bar.progress(current / total)
                st.session_state["af_batch_progress"] = current
                current_text.write(
                    f"Row {current}/{total} · Application {row.get('applicationIdentifier', '')}"
                )
                if result.get("requestStatus") == "Request successful":
                    counters["success"] += 1
                    counters["alert" if result.get("alertFlg") else "no_alert"] += 1
                else:
                    counters["failed"] += 1
                metric_columns[0].metric("Successful", counters["success"])
                metric_columns[1].metric("Failed", counters["failed"])
                metric_columns[2].metric("Alerts", counters["alert"])
                metric_columns[3].metric("No alerts", counters["no_alert"])

            try:
                sent_results = execute_application_batch(
                    validation.valid_rows,
                    endpoint=endpoint,
                    timeout_seconds=float(batch_timeout),
                    verify_tls=verify_tls,
                    ca_bundle=ca_bundle,
                    delay_seconds=float(delay_seconds),
                    stop_on_error=stop_mode == "Stop batch",
                    progress=update_progress,
                )
                for item in sent_results:
                    if not item.get("alertFlg") or not isinstance(
                        item.get("_request"), dict
                    ):
                        continue
                    batch_response = SasRuntimeResponse(
                        int(item.get("httpStatus") or 0),
                        int(item.get("processingTimeMs") or 0),
                        {},
                        str(item.get("_rawResponse") or ""),
                        item.get("_parsedResponse"),
                        None,
                    )
                    _record_alert_if_created(
                        item["_request"], batch_response, show_dialog=False
                    )
                all_results = invalid_batch_results(validation) + sent_results
                st.session_state["af_batch_results"] = sorted(
                    all_results, key=lambda item: item["rowNumber"]
                )
                st.session_state["af_batch_details"] = {
                    int(item["rowNumber"]): {
                        "request": item.get("_request"),
                        "response": item.get("_parsedResponse"),
                        "rawResponse": item.get("_rawResponse"),
                    }
                    for item in all_results
                }
                st.session_state["af_batch_status"] = "completed"
            except Exception as error:  # UI boundary: never expose a stack trace.
                st.session_state["af_batch_status"] = "failed"
                st.error(f"Batch stopped because of an unexpected error: {error}")
            finally:
                finish_batch_run(st.session_state, fingerprint)

    results = st.session_state.get("af_batch_results", [])
    if results:
        _render_batch_results(results)


PROFILE_COUNT_FIELDS = (
    "disbAcctCustCnt30d",
    "refPhoneCustCnt30d",
    "addressCustCnt30d",
    "clusterCustCnt30d",
)


def _find_profile_counts(profiles: Any) -> dict[str, Any]:
    """Pull the well-known 30-day counters out of whatever shape SAS returned."""

    found: dict[str, Any] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in PROFILE_COUNT_FIELDS and key not in found:
                    found[key] = value
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(profiles)
    return found


def _build_quick_demo_dialog_entry(
    spec: DemoSpec, last_payload: dict[str, Any], last_response: SasRuntimeResponse
) -> dict[str, Any] | None:
    """Build the Quick Demo popup content for the FINAL (trigger) step only.

    Returns None whenever the final step did not create an alert. Callers must
    never invoke this for a seed/intermediate step — only the last entry of a
    demo sequence is allowed to open a popup.
    """

    if last_response.parsed_body is None:
        return None
    summary = summarize_sas_response(last_response.parsed_body)
    if not summary.alert_created:
        return None

    fired_rules = extract_application_fired_rules(last_response.parsed_body)
    target_hit_rule = next(
        (rule for rule in fired_rules if _rule_matches_target(rule, spec.target_rule)),
        None,
    )
    actual_rule = target_hit_rule or (fired_rules[0] if fired_rules else None)
    message = last_payload["message"]
    return {
        "target_rule": spec.target_rule,
        "actual_rule_name": actual_rule.display_name if actual_rule else "Unknown rule",
        "reason": actual_rule.reason if actual_rule else None,
        "application_identifier": message["application"]["identifier"],
        "customer_identifier": message["customer"]["identifier"],
        "alert_id": normalize_application_result(
            last_response.parsed_body,
            payload=last_payload,
            http_status=last_response.status_code,
            elapsed_ms=last_response.elapsed_ms,
            parse_error=last_response.parse_error,
        ).alert_id,
    }


def _render_demo_result(spec: DemoSpec, results: list[dict[str, Any]]) -> None:
    _section("Kết quả hồ sơ mẫu")

    # 1. Steps
    step_rows = []
    progression_rows = []
    for entry in results:
        response: SasRuntimeResponse | None = entry.get("response")
        fired_rules = (
            extract_application_fired_rules(response.parsed_body)
            if response is not None and response.parsed_body is not None
            else []
        )
        summary = (
            summarize_sas_response(response.parsed_body)
            if response is not None and response.parsed_body is not None
            else None
        )
        step_rows.append(
            {
                "Giai đoạn": (
                    "Chuẩn bị lịch sử" if entry is not results[-1] else "Hồ sơ hiện tại"
                ),
                "HTTP": response.status_code if response is not None else "—",
                "Fired rules": ", ".join(r.display_name for r in fired_rules) or "—",
                "Alert": "Yes" if summary and summary.alert_created else "No",
            }
        )
        profiles = (
            response.parsed_body.get("profiles")
            if response is not None and isinstance(response.parsed_body, dict)
            else None
        )
        counts = _find_profile_counts(profiles) if profiles else {}
        if counts:
            progression_rows.append({"Step": entry["label"], **counts})

    with st.expander("Tiến trình minh họa", expanded=False):
        st.dataframe(step_rows, use_container_width=True, hide_index=True)

    last_entry = results[-1]
    if last_entry.get("errors"):
        st.error("Hồ sơ mẫu không hợp lệ: " + " | ".join(last_entry["errors"]))
        return
    last_response: SasRuntimeResponse | None = last_entry.get("response")
    if last_response is None:
        st.warning("Không thể hoàn tất phần chuẩn bị lịch sử minh họa.")
        return
    if not (200 <= last_response.status_code < 300):
        st.error(
            f"The final request returned HTTP {last_response.status_code}; the demo sequence stopped."
        )

    # Profile values are returned by SAS and remain diagnostic-only.

    fired_rules = (
        extract_application_fired_rules(last_response.parsed_body)
        if last_response.parsed_body is not None
        else []
    )
    target_hit = any(
        _rule_matches_target(rule, spec.target_rule) for rule in fired_rules
    )

    # 3. Target rule — never treated as proof by itself, see step 4 below.
    if target_hit:
        st.success("Kịch bản minh họa đã tạo đúng kết quả kỳ vọng.")
    else:
        st.warning(
            "Kịch bản demo không tạo ra kết quả kỳ vọng. "
            f"Expected: {spec.target_rule}. Actual: Không có matching rule returned."
        )

    # 4. Actual fired rule(s) from SAS — the only source of truth.
    st.markdown("**Quy tắc thực tế SAS trả về cho hồ sơ hiện tại:**")
    _render_fired_rules_table(fired_rules)

    # 5. Alert
    summary = summarize_sas_response(last_response.parsed_body)
    st.markdown(f"**Cảnh báo:** {'Đã tạo' if summary.alert_created else 'Không tạo'}")
    _render_alerted_entities_section(summary.alerted_entities)

    # 6. Technical details
    with st.expander("Technical Details — Request/Response by Step", expanded=False):
        if progression_rows:
            st.markdown("**Profile progression returned by SAS**")
            st.dataframe(progression_rows, use_container_width=True, hide_index=True)
        for entry in results:
            st.markdown(f"**{entry['label']}**")
            st.json(entry["payload"], expanded=False)
            response = entry.get("response")
            if response is not None:
                st.json(response.parsed_body, expanded=False)


def _render_quick_demos(
    *, endpoint: str, timeout_seconds: float, verify_tls: bool, ca_bundle: str | None
) -> None:
    pending_demo_dialog = st.session_state.get("af_demo_pending_dialog")
    if pending_demo_dialog:
        _show_quick_demo_result_dialog(pending_demo_dialog)

    _section("Hồ sơ mẫu có hướng dẫn")
    st.caption(
        "Dữ liệu hoàn toàn tổng hợp. Với kịch bản mạng lưới, hệ thống sẽ chuẩn bị lịch sử "
        "thật trên SAS trước khi sàng lọc hồ sơ hiện tại."
    )
    option_to_key = {
        "Shared Disbursement Account · Tài khoản giải ngân dùng chung": "demo1",
        "Shared Reference Network · Mạng lưới điện thoại tham chiếu": "demo2",
        "Linked Address Network · Mạng lưới địa chỉ liên kết": "demo3",
    }
    selected = st.selectbox(
        "Chọn hồ sơ mẫu",
        list(option_to_key),
        key="af_guided_demo_selection",
    )
    key = option_to_key[selected]
    spec = DEMO_SPECS[key]
    st.caption(spec.intro)
    if st.button(
        "Chuẩn bị dữ liệu mẫu & chạy sàng lọc",
        type="primary",
        use_container_width=True,
        key="af_guided_demo_run",
    ):
        steps = spec.build_steps()
        with st.status("Đang chuẩn bị kịch bản", expanded=True) as status:
            st.write("Đang chuẩn bị lịch sử minh họa...")
            demo_results = run_demo_steps(
                steps,
                endpoint=endpoint,
                timeout_seconds=timeout_seconds,
                verify_tls=verify_tls,
                ca_bundle=ca_bundle,
            )
            st.write("Đang sàng lọc hồ sơ hiện tại...")
            st.write("Đã nhận quyết định.")
            status.update(label="Hoàn tất kịch bản", state="complete", expanded=False)
        for entry in demo_results:
            response = entry.get("response")
            if response is not None:
                _record_alert_if_created(entry["payload"], response, show_dialog=False)
        st.session_state[f"af_{key}_result"] = demo_results

        last_demo_entry = demo_results[-1]
        last_demo_response = last_demo_entry.get("response")
        dialog_entry = (
            _build_quick_demo_dialog_entry(
                spec, last_demo_entry["payload"], last_demo_response
            )
            if last_demo_response is not None
            else None
        )
        if dialog_entry is not None:
            st.session_state["af_demo_pending_dialog"] = dialog_entry
            st.rerun()

    demo_results = st.session_state.get(f"af_{key}_result")
    if demo_results:
        _render_demo_result(spec, demo_results)


def _description_endpoint(execute_endpoint: str) -> str | None:
    """Derive .../decision/description from the .../decision/execute endpoint."""

    trimmed = execute_endpoint.rstrip("/")
    if trimmed.endswith("/execute"):
        return trimmed[: -len("/execute")] + "/description"
    return None


def _runtime_schema_version(description: dict[str, Any], schema_name: str) -> Any:
    """Read organization.schemas[].version for schema_name — real shape, e.g.:
    {"organization": {"schemas": [{"name": "Application Fraud", "version": "2.11.0"}, ...]}}
    """

    organization = description.get("organization")
    schemas = organization.get("schemas") if isinstance(organization, dict) else None
    if isinstance(schemas, list):
        for schema in schemas:
            if isinstance(schema, dict) and schema.get("name") == schema_name:
                return schema.get("version")
    return None


def _render_runtime_status(
    *, endpoint: str, timeout_seconds: float, verify_tls: bool, ca_bundle: str | None
) -> None:
    """Read-only runtime status from GET .../decision/description.

    Never blocks or breaks Execute: a failed/unreachable description fetch
    just shows 'Runtime metadata unavailable', nothing else changes.
    """

    description_endpoint = _description_endpoint(endpoint)
    description = (
        fetch_runtime_description(
            endpoint=description_endpoint,
            timeout_seconds=timeout_seconds,
            verify_tls=verify_tls,
            ca_bundle=ca_bundle,
        )
        if description_endpoint
        else None
    )

    with st.expander("Chi tiết kỹ thuật hệ thống", expanded=False):
        if description is not None:
            columns = st.columns(3)
            columns[0].metric("Runtime", "Online")
            columns[1].metric("Build", description.get("build", "—"))
            columns[2].metric(
                "Application Fraud schema",
                _runtime_schema_version(description, "Application Fraud") or "—",
            )
        else:
            st.info("Runtime metadata unavailable")
        st.text_input(
            "Expected package version (development only)",
            value="",
            placeholder="Example: 50217",
            key="af_dev_expected_package_version",
            help=(
                "Compare manually with message.sas.system.packageVersion in the response. "
                "This value does not affect execution."
            ),
        )
        if description is not None:
            st.json(description, expanded=False)
        elif description_endpoint:
            st.caption(f"Could not retrieve metadata from {description_endpoint}.")
        else:
            st.caption(
                "The description endpoint could not be derived from the current decision endpoint "
                "(it must end with '/execute')."
            )


def render_application_workspace(
    *, endpoint: str, timeout_seconds: float, verify_tls: bool, ca_bundle: str | None
) -> None:
    _initialize_state()
    _render_styles()
    st.markdown(
        f"""
        <div class="af-console-header">
          <div class="af-eyebrow">Loan Origination & Fraud Screening</div>
          <h2>Không gian xử lý hồ sơ</h2>
          <p>Người dùng: {os.getenv('BANK_DEMO_USER', 'Teller 01')} &nbsp;·&nbsp;
          Chi nhánh: {os.getenv('BANK_DEMO_BRANCH', 'HCM Demo Branch')} &nbsp;·&nbsp;
          Môi trường: POC</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _render_runtime_status(
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        verify_tls=verify_tls,
        ca_bundle=ca_bundle,
    )

    single_tab, batch_tab, quick_demo_tab = st.tabs(
        ["Hồ sơ mới", "Xử lý hồ sơ hàng loạt", "Hồ sơ mẫu"]
    )
    with single_tab:
        _render_single(
            endpoint=endpoint,
            timeout_seconds=timeout_seconds,
            verify_tls=verify_tls,
            ca_bundle=ca_bundle,
        )
    with batch_tab:
        _render_batch(
            endpoint=endpoint,
            timeout_seconds=timeout_seconds,
            verify_tls=verify_tls,
            ca_bundle=ca_bundle,
        )
    with quick_demo_tab:
        _render_quick_demos(
            endpoint=endpoint,
            timeout_seconds=timeout_seconds,
            verify_tls=verify_tls,
            ca_bundle=ca_bundle,
        )
