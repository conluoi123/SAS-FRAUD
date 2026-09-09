"""Operational Streamlit workspace for Application Fraud only."""

from __future__ import annotations

import hashlib
import random
import uuid
from datetime import datetime, timezone
from typing import Any, MutableMapping

import requests
import streamlit as st

try:
    from .alert_log import record_alert
    from .application_batch import (
        RESULT_COLUMNS,
        application_csv_template,
        claim_batch_run,
        execute_application_batch,
        finish_batch_run,
        invalid_batch_results,
        parse_application_csv,
        reset_batch_for_new_file,
        results_to_csv,
    )
    from .application_config import (
        AF_CIC_PROFILE_CAPACITY,
        APPLICATION_ACTIVITY_TYPE,
        APPLICATION_AUTHENTICATION_TYPE,
        APPLICATION_CHANNELS,
        APPLICATION_CUSTOMER_TYPE,
        APPLICATION_ORIGINATION_TYPE,
    )
    from .application_demo import DEMO_SPECS, DemoSpec, run_demo_steps
    from .payloads import (
        build_application_fraud_payload,
        validate_application_fraud_payload,
    )
    from .sas_client import SasRuntimeResponse, fetch_runtime_description, send_message
    from .sas_response import (
        ApplicationFiredRule,
        extract_application_fired_rules,
        extract_return_fields,
        summarize_sas_response,
    )
except ImportError:
    from alert_log import record_alert
    from application_batch import (
        RESULT_COLUMNS,
        application_csv_template,
        claim_batch_run,
        execute_application_batch,
        finish_batch_run,
        invalid_batch_results,
        parse_application_csv,
        reset_batch_for_new_file,
        results_to_csv,
    )
    from application_config import (
        AF_CIC_PROFILE_CAPACITY,
        APPLICATION_ACTIVITY_TYPE,
        APPLICATION_AUTHENTICATION_TYPE,
        APPLICATION_CHANNELS,
        APPLICATION_CUSTOMER_TYPE,
        APPLICATION_ORIGINATION_TYPE,
    )
    from application_demo import DEMO_SPECS, DemoSpec, run_demo_steps
    from payloads import (
        build_application_fraud_payload,
        validate_application_fraud_payload,
    )
    from sas_client import SasRuntimeResponse, fetch_runtime_description, send_message
    from sas_response import (
        ApplicationFiredRule,
        extract_application_fired_rules,
        extract_return_fields,
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


def _render_styles() -> None:
    st.markdown(
        """
        <style>
        .af-console-header {
            background: #f7f9fc;
            border: 1px solid #d8dee8;
            border-left: 4px solid #17365d;
            border-radius: 4px;
            padding: 16px 18px;
            margin: 0 0 16px 0;
        }
        .af-console-header h2 { color: #17365d; font-size: 1.35rem; margin: 0; }
        .af-console-header p { color: #4b5563; margin: 5px 0 0 0; }
        .af-section-title {
            color: #17365d;
            font-size: 1rem;
            font-weight: 650;
            border-bottom: 1px solid #d8dee8;
            padding-bottom: 6px;
            margin: 6px 0 10px 0;
        }
        .af-contract-note {
            background: #f7f9fc;
            border: 1px solid #d8dee8;
            border-radius: 3px;
            color: #374151;
            padding: 10px 12px;
        }
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


def _fired_rules_table_rows(fired_rules: list[ApplicationFiredRule]) -> list[dict[str, Any]]:
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
    st.dataframe(_fired_rules_table_rows(fired_rules), use_container_width=True, hide_index=True)


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


@st.dialog("Application Result")
def _show_application_result_dialog(entry: dict[str, Any]) -> None:
    outcome_name = str(entry.get("outcome_name") or "").lower()
    if "declin" in outcome_name or "reject" in outcome_name:
        st.markdown("## :material/block: Application Declined")
    else:
        st.markdown("## :material/warning: Application Alert")

    fired_rules = entry.get("fired_rules") or []
    if fired_rules:
        for rule in fired_rules:
            st.markdown(f"**Rule:** `{rule.get('name', '')}`")
            if rule.get("reason"):
                st.markdown(f"**Reason:** {rule['reason']}")
    else:
        st.caption("SAS did not return a specific rule name with this alert.")

    st.caption(f"Application: {entry.get('application_identifier', '')}")
    st.caption(f"Customer: {entry.get('customer_identifier', '')}")
    st.markdown("**Alert:** Created")

    if st.button("Close", type="primary", use_container_width=True, key="af_manual_dialog_close"):
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
    st.markdown("**Alert:** Created")

    if st.button("Close", type="primary", use_container_width=True, key="af_demo_dialog_close"):
        st.session_state["af_demo_pending_dialog"] = None
        st.rerun()


def _record_alert_if_created(
    payload: dict[str, Any], response: SasRuntimeResponse, *, show_dialog: bool = True
) -> None:
    if response.parsed_body is None:
        return
    summary = summarize_sas_response(response.parsed_body)
    if not summary.alert_created:
        return

    fired_rules = extract_application_fired_rules(response.parsed_body)
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
            "transaction_identifier": message["sas"]["system"]["transactionIdentifier"],
            "actual_alert": summary.alert_created,
            "fired_rules": [rule.display_name for rule in fired_rules],
            "fired_rule_identifiers": [
                rule.rule_identifier or rule.display_name for rule in fired_rules
            ],
            "http_status": response.status_code,
            "outcome_name": summary.outcome_name,
            "alerted_entities": summary.alerted_entities,
            "rule_fired": bool(fired_rules),
        }
    )
    if show_dialog:
        st.session_state["af_pending_result_dialog"] = {
            "outcome_name": summary.outcome_name,
            "application_identifier": message["application"]["identifier"],
            "customer_identifier": message["customer"]["identifier"],
            "fired_rules": [
                {"name": rule.display_name, "reason": rule.reason} for rule in fired_rules
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
    return_fields = extract_return_fields(response.parsed_body)
    summary = (
        summarize_sas_response(response.parsed_body)
        if response.parsed_body is not None
        else None
    )
    fired_rules = (
        extract_application_fired_rules(response.parsed_body)
        if response.parsed_body is not None
        else []
    )
    alert = summary.alert_created if summary else False
    request_ok = 200 <= response.status_code < 300 and response.parse_error is None

    _section("Application Result")
    st.markdown(
        f"**Application:** `{identity['application_identifier']}`  \n"
        f"**Transaction:** `{identity['transaction_identifier']}`  \n"
        f"**Customer:** `{identity['customer_identifier']}`  \n"
        f"**Processed at:** {identity['sent_at']}"
    )

    status_columns = st.columns(3)
    status_columns[0].metric(
        "Request", "Successful" if request_ok else "Failed"
    )
    status_columns[1].metric("Rule", "Fired" if fired_rules else "Not fired")
    status_columns[2].metric("Alert", "Created" if alert else "No alert")

    outcome_raw = (summary.outcome_name or summary.outcome) if summary else None
    outcome_display = _display_outcome(outcome_raw)
    detail_columns = st.columns(4)
    detail_columns[0].metric("HTTP status", response.status_code)
    detail_columns[1].metric("Round trip", f"{response.elapsed_ms} ms")
    detail_columns[2].metric("returnType", return_fields.get("returnType"))
    detail_columns[3].metric("SAS outcome", outcome_display)
    if outcome_raw is not None and outcome_display != str(outcome_raw).strip():
        st.caption(f"Raw outcomeName: {outcome_raw}")
    if return_fields.get("returnDesc") or return_fields.get("returnDetails"):
        st.caption(
            " | ".join(
                str(value)
                for value in (
                    return_fields.get("returnDesc"),
                    return_fields.get("returnDetails"),
                )
                if value is not None
            )
        )

    _section("Fired rules")
    _render_fired_rules_table(fired_rules)
    if alert:
        st.info(
            "SAS evaluated this alert against existing Profile history. Reusing a prior "
            "test key such as an identity number, account or reference phone can therefore "
            "produce a valid alert based on earlier submissions."
        )

    if summary:
        _render_alerted_entities_section(summary.alerted_entities)

    profiles = (
        response.parsed_body.get("profiles")
        if isinstance(response.parsed_body, dict)
        else None
    )
    if profiles is not None:
        with st.expander("Returned Profiles", expanded=False):
            st.json(profiles, expanded=False)
    with st.expander("Raw SAS Response", expanded=False):
        if response.parse_error:
            st.error(f"Invalid JSON response: {response.parse_error}")
        st.code(response.raw_body, language="text", wrap_lines=True)
    with st.expander("Request JSON", expanded=False):
        st.json(payload, expanded=False)


def _render_single(
    *, endpoint: str, timeout_seconds: float, verify_tls: bool, ca_bundle: str | None
) -> None:
    # Rendered only inside the manual tab — Quick Demo has its own independent
    # af_demo_pending_dialog/_show_quick_demo_result_dialog (see _render_quick_demos).
    pending_dialog = st.session_state.get("af_pending_result_dialog")
    if pending_dialog:
        _show_application_result_dialog(pending_dialog)

    now = datetime.now(timezone.utc).replace(microsecond=0)
    channel_codes = list(APPLICATION_CHANNELS)

    _section("Test Data Management")
    reset_col1, reset_col2 = st.columns(2)
    if reset_col1.button(
        "New Application - Keep Customer",
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
        "Create Fresh Test Dataset",
        key="af_reset_fresh_dataset",
        use_container_width=True,
        help=(
            "Generate new values for every Profile key before a normal no-alert test. "
            "This does not delete any Profile stored by SAS."
        ),
    ):
        apply_fresh_test_dataset(st.session_state)
        st.rerun()

    with st.form("af_single_form", border=True):
        _section("1. Application Details")
        first, second = st.columns(2)
        application_identifier = first.text_input("Application ID", key="af_single_application_id")
        application_type = second.selectbox(
            "Loan Product", ["PERSONAL_LOAN", "HOME_LOAN", "AUTO_LOAN"]
        )
        application_amount = first.number_input(
            "Requested Amount", min_value=0.0, value=50_000_000.0, step=1_000_000.0
        )
        currency_code = second.selectbox("Currency", ["VND", "USD"])
        application_purpose = first.selectbox(
            "Loan Purpose", ["PERSONAL_USE", "HOME_RENOVATION", "VEHICLE_PURCHASE"]
        )
        application_status = second.selectbox(
            "Application Status", ["SUBMITTED", "PENDING", "APPROVED"]
        )
        application_stage = first.selectbox(
            "Application Stage", ["UNDER_REVIEW", "DOCUMENT_CHECK", "DECISION"]
        )
        event_date = second.date_input("Event Date (UTC)", value=now.date())
        event_time = first.time_input("Event Time (UTC)", value=now.time())

        _section("2. Applicant and Customer")
        first, second = st.columns(2)
        applicant_identifier = first.text_input(
            "Applicant ID", key="af_single_applicant_id"
        )
        applicant_name = second.text_input("Applicant Name", "Nguyen Van Demo")
        customer_identifier = first.text_input(
            "Customer ID", key="af_single_customer_id"
        )
        customer_name = second.text_input("Customer Name", "Nguyen Van Demo")
        customer_type = first.selectbox("Customer Type", ["INDIVIDUAL", "BUSINESS"])
        address_country_code = second.text_input("Country Code", "VN", max_chars=3)

        _section("3. Identity and Contact")
        first, second = st.columns(2)
        identification_number = first.text_input(
            "Identification Number", key="af_single_identification_number"
        )
        email = second.text_input("Email", "demo.application@example.com")
        phone = first.text_input("Phone Number", key="af_single_phone")
        months_at_location = second.number_input(
            "Months at Address", min_value=0, value=24, step=1
        )

        _section("4. Employment and Income")
        first, second = st.columns(2)
        employer_name = first.text_input("Employer Name", "Demo Company")
        employment_status = second.selectbox(
            "Employment Status", ["EMPLOYED", "SELF_EMPLOYED", "UNEMPLOYED"]
        )
        monthly_income = first.number_input(
            "Monthly Regular Income",
            min_value=0.0,
            value=25_000_000.0,
            step=1_000_000.0,
        )
        outstanding_debt = second.number_input(
            "Outstanding Debt", min_value=0.0, value=5_000_000.0, step=1_000_000.0
        )

        _section("5. Submission Channel")
        application_channel = st.selectbox(
            "Application Channel",
            channel_codes,
            index=channel_codes.index("MOBILE_APP"),
            format_func=lambda code: APPLICATION_CHANNELS[code]["label"],
        )
        st.caption(
            "application.channel and solution.channelType use the centralized POC mapping."
        )

        _section("6. Device Information")
        first, second = st.columns(2)
        device_identifier = first.text_input("Device ID", key="af_single_device_id")
        ip_address = second.text_input("IP Address", "203.0.113.42")

        _section("7. CIC")
        st.markdown(
            f'<div class="af-contract-note">SAS manages the AF_CICIdentity Profile. '
            f'Both Profile arrays use capacity {AF_CIC_PROFILE_CAPACITY}. The UI does not '
            "edit Profile counts or send unverified CIC paths.</div>",
            unsafe_allow_html=True,
        )

        _section("8. Application Fraud Risk Data")
        first, second = st.columns(2)
        bank_id = first.text_input("Institution ID", "BANK-A")
        sales_agent_identifier = second.text_input(
            "Sales Agent ID", key="af_single_sales_agent"
        )
        disb_account_number = first.text_input(
            "Disbursement Account", key="af_single_disb_account"
        )
        reference_phone = second.text_input(
            "Reference Phone", key="af_single_reference_phone"
        )
        normalized_address = st.text_input(
            "Normalized Address", key="af_single_normalized_address"
        )
        disb_owner_match = first.checkbox("Account Owner Matches Applicant", value=True)
        employer_unverified = second.checkbox("Employer Unverified", value=False)
        st.caption("SAS Profiles and Variable Rules calculate all 7-day and 30-day windows.")

        _section("9. Technical Information")
        st.code(
            f"originationType={APPLICATION_ORIGINATION_TYPE} | "
            f"activityType={APPLICATION_ACTIVITY_TYPE} | "
            f"authenticationType={APPLICATION_AUTHENTICATION_TYPE} | "
            f"customerType={APPLICATION_CUSTOMER_TYPE}\n"
            f"transactionIdentifier={st.session_state['af_single_transaction_id']}",
            language="text",
        )
        submitted = st.form_submit_button(
            "Submit Application", type="primary", use_container_width=True
        )

    values = {
        "message_datetime": _utc_string(event_date, event_time),
        "application_identifier": application_identifier,
        "transaction_identifier": st.session_state["af_single_transaction_id"],
        "application_type": application_type,
        "application_amount": application_amount,
        "currency_code": currency_code,
        "application_channel": application_channel,
        "application_purpose": application_purpose,
        "application_status": application_status,
        "application_stage": application_stage,
        "applicant_identifier": applicant_identifier,
        "applicant_name": applicant_name,
        "monthly_regular_income": monthly_income,
        "outstanding_debt": outstanding_debt,
        "employer_name": employer_name,
        "employment_status": employment_status,
        "customer_identifier": customer_identifier,
        "customer_name": customer_name,
        "customer_type": customer_type,
        "address_country_code": address_country_code.upper(),
        "identification_number": identification_number,
        "email": email,
        "phone": phone,
        "months_at_location": months_at_location,
        "device_identifier": device_identifier,
        "device_ip_address": ip_address,
        "app_risk": {
            "bankId": bank_id,
            "salesAgentIdentifier": sales_agent_identifier,
            "disbAcctNumber": disb_account_number,
            "referencePhone": reference_phone,
            "normalizedAddress": normalized_address,
            "disbAcctOwnerMatchInd": int(disb_owner_match),
            "employerUnverifiedInd": int(employer_unverified),
        },
    }
    try:
        payload = build_application_fraud_payload(values)
        validation_errors = validate_application_fraud_payload(payload)
    except ValueError as error:
        payload = None
        validation_errors = [str(error)]

    _section("Payload Preview")
    if payload is not None:
        st.json(payload, expanded=False)
    for error in validation_errors:
        st.error(error)

    if submitted:
        transaction_id = st.session_state["af_single_transaction_id"]
        if st.session_state["af_single_sending"] or (
            st.session_state["af_single_last_transaction"] == transaction_id
        ):
            st.warning("This request was already submitted; reruns will not submit it again.")
        elif validation_errors or payload is None:
            st.error("The payload is invalid; no request was submitted.")
        else:
            st.session_state["af_single_sending"] = True
            st.session_state["af_single_result"] = None

            try:
                with st.spinner("Waiting for SAS Fraud Runtime..."):
                    response = send_message(
                        endpoint=endpoint,
                        payload=payload,
                        timeout_seconds=timeout_seconds,
                        verify_tls=verify_tls,
                        ca_bundle=ca_bundle,
                    )
                st.session_state["af_single_result"] = {
                    "payload": payload,
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

                _record_alert_if_created(payload, response)
                if st.session_state.get("af_pending_result_dialog"):
                    # Setting session_state alone does not reopen a @st.dialog —
                    # it only takes effect on the NEXT script run, so force one.
                    st.rerun()
            except requests.exceptions.SSLError as error:
                st.session_state["af_single_last_transaction"] = None
                st.error(f"SSL error: {error}")
            except requests.exceptions.Timeout as error:
                st.session_state["af_single_last_transaction"] = None
                st.error(f"Timeout: {error}")
            except requests.exceptions.ConnectionError as error:
                st.session_state["af_single_last_transaction"] = None
                st.error(f"DNS/connection error: {error}")
            except (requests.RequestException, ValueError) as error:
                st.session_state["af_single_last_transaction"] = None
                st.error(f"Submission failed: {error}")
            finally:
                st.session_state["af_single_sending"] = False

    result = st.session_state.get("af_single_result")
    if result:
        _render_single_result(result)


def _filtered_results(results: list[dict[str, Any]], selected: str) -> list[dict[str, Any]]:
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
        return [result for result in results if result.get("requestStatus") == "Submission failed"]
    if selected == "Invalid rows":
        return [
            result
            for result in results
            if result.get("requestStatus") == "Invalid payload"
        ]
    return results


def _render_batch_results(results: list[dict[str, Any]]) -> None:
    _section("Processing Results")
    success = sum(item.get("requestStatus") == "Request successful" for item in results)
    failed = sum(item.get("requestStatus") == "Submission failed" for item in results)
    alert = sum(bool(item.get("alertFlg")) for item in results)
    no_alert = sum(
        item.get("requestStatus") == "Request successful" and not item.get("alertFlg")
        for item in results
    )
    columns = st.columns(4)
    columns[0].metric("Successful", success)
    columns[1].metric("Failed", failed)
    columns[2].metric("Alerts", alert)
    columns[3].metric("No alerts", no_alert)

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
    st.dataframe(
        [{column: row.get(column) for column in RESULT_COLUMNS} for row in filtered],
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Download Results CSV",
        data=results_to_csv(results),
        file_name="application_fraud_batch_results.csv",
        mime="text/csv",
        key="af_download_results",
        use_container_width=True,
    )
    if filtered:
        labels = [
            f"Row {item['rowNumber']} — {item['applicationIdentifier']}" for item in filtered
        ]
        selected_label = st.selectbox("Row details", labels, key="af_result_detail")
        detail = filtered[labels.index(selected_label)]
        with st.expander("Request JSON", expanded=False):
            if detail.get("_request") is None:
                st.info("The invalid row was not mapped or submitted.")
            else:
                st.json(detail["_request"], expanded=False)
        with st.expander("Response Details", expanded=False):
            if detail.get("_parsedResponse") is not None:
                st.json(detail["_parsedResponse"], expanded=False)
            elif detail.get("_rawResponse"):
                st.code(detail["_rawResponse"], language="text", wrap_lines=True)
            else:
                st.info(detail.get("errorMessage") or "No runtime response is available.")


def _render_batch(
    *, endpoint: str, timeout_seconds: float, verify_tls: bool, ca_bundle: str | None
) -> None:
    st.download_button(
        "Download CSV Template",
        data=application_csv_template(),
        file_name="application_fraud_template.csv",
        mime="text/csv",
        key="af_download_template",
        use_container_width=True,
    )
    uploaded = st.file_uploader(
        "Upload CSV", type=["csv"], key="af_csv_upload", accept_multiple_files=False
    )
    if uploaded is None:
        st.info("Download the template, enter data, then upload it for validation before submission.")
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

    _section("Data Validation")
    st.caption(
        f"{len(validation.rows)} data rows · {len(validation.valid_rows)} valid · "
        f"{len(validation.errors)} errors"
    )
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
        st.success("All rows are valid.")

    first, second, third = st.columns(3)
    delay_seconds = first.number_input(
        "Delay between requests (seconds)",
        min_value=0.0,
        max_value=60.0,
        value=0.5,
        step=0.1,
        key="af_batch_delay",
    )
    batch_timeout = second.number_input(
        "Timeout per request (seconds)",
        min_value=1.0,
        max_value=300.0,
        value=float(timeout_seconds),
        step=1.0,
        key="af_batch_timeout",
    )
    stop_mode = third.selectbox(
        "On error", ["Continue", "Stop batch"], key="af_batch_stop_mode"
    )
    confirmed = st.checkbox(
        "I have reviewed the data; submit valid rows only.", key="af_batch_confirm"
    )
    already_completed = (
        st.session_state.get("af_batch_completed_fingerprint") == fingerprint
    )
    run_clicked = st.button(
        "Run Batch",
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
            st.warning("The batch is running or has completed; duplicate submission was blocked.")
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
    }


def _render_demo_result(spec: DemoSpec, results: list[dict[str, Any]]) -> None:
    _section(spec.title)

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
                "Step": entry["label"],
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

    st.dataframe(step_rows, use_container_width=True, hide_index=True)

    last_entry = results[-1]
    if last_entry.get("errors"):
        st.error("Invalid payload: " + " | ".join(last_entry["errors"]))
        return
    last_response: SasRuntimeResponse | None = last_entry.get("response")
    if last_response is None:
        st.warning("The demo sequence stopped because an earlier step failed.")
        return
    if not (200 <= last_response.status_code < 300):
        st.error(
            f"The final request returned HTTP {last_response.status_code}; the demo sequence stopped."
        )

    # 2. Profile progression
    if progression_rows:
        st.markdown("**Profile progression returned by SAS:**")
        st.dataframe(progression_rows, use_container_width=True, hide_index=True)

    fired_rules = (
        extract_application_fired_rules(last_response.parsed_body)
        if last_response.parsed_body is not None
        else []
    )
    target_hit = any(_rule_matches_target(rule, spec.target_rule) for rule in fired_rules)

    # 3. Target rule — never treated as proof by itself, see step 4 below.
    st.markdown(f"**Target rule:** `{spec.target_rule}`")
    if target_hit:
        st.success("Target rule result: PASS")
    else:
        st.warning(f"Target rule result: NO HIT — {spec.no_hit_message}")

    # 4. Actual fired rule(s) from SAS — the only source of truth.
    st.markdown("**Actual rules returned by SAS for the final step:**")
    _render_fired_rules_table(fired_rules)

    # 5. Alert
    summary = summarize_sas_response(last_response.parsed_body)
    st.markdown(f"**Alert:** {'Created' if summary.alert_created else 'Not created'}")
    _render_alerted_entities_section(summary.alerted_entities)

    # 6. Technical details
    with st.expander("Technical Details — Request/Response by Step", expanded=False):
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

    _section("Quick Alert Demo")
    st.caption(
        "Each demo submits a real sequence of Application Fraud requests to SAS through "
        "build_application_fraud_payload() and send_message(). Results and profile counts "
        "are never simulated by Streamlit."
    )

    demo_columns = st.columns(3)
    for index, key in enumerate(("demo1", "demo2", "demo3")):
        spec = DEMO_SPECS[key]
        with demo_columns[index]:
            st.caption(spec.intro)
            if st.button(
                spec.title,
                type="primary" if index == 0 else "secondary",
                use_container_width=True,
                key=f"af_{key}_run",
            ):
                steps = spec.build_steps()
                with st.spinner(f"Running {spec.title}..."):
                    demo_results = run_demo_steps(
                        steps,
                        endpoint=endpoint,
                        timeout_seconds=timeout_seconds,
                        verify_tls=verify_tls,
                        ca_bundle=ca_bundle,
                    )
                for entry in demo_results:
                    response = entry.get("response")
                    if response is not None:
                        # Alert-log recording only — af_demo_pending_dialog (below) is
                        # the only path allowed to open a popup, and only for the
                        # final/trigger step, never a seed step.
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
                    # Setting session_state alone does not reopen a @st.dialog —
                    # it only takes effect on the NEXT script run, so force one.
                    st.rerun()

    for key in ("demo1", "demo2", "demo3"):
        demo_results = st.session_state.get(f"af_{key}_result")
        if demo_results:
            _render_demo_result(DEMO_SPECS[key], demo_results)


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

    with st.expander("Developer diagnostics", expanded=False):
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
        """
        <div class="af-console-header">
          <h2>Application Fraud</h2>
          <p>Test application submissions against SAS Fraud Runtime</p>
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

    quick_demo_tab, single_tab, batch_tab = st.tabs(
        ["Quick Alert Demo", "Single Application", "CSV Batch Submission"]
    )
    with quick_demo_tab:
        _render_quick_demos(
            endpoint=endpoint,
            timeout_seconds=timeout_seconds,
            verify_tls=verify_tls,
            ca_bundle=ca_bundle,
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
