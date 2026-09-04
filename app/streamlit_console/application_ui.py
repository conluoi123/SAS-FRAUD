"""Streamlit UI for the Application Fraud synthetic POC."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timezone
from typing import Any, Callable

import requests
import streamlit as st

try:
    from .alert_log import record_alert
    from .application_scenarios import (
        APPLICATION_SCENARIOS,
        ApplicationScenario,
        calculate_30d_counts,
        expected_application_rules,
        normalize_address,
        scenario_history,
    )
    from .payloads import (
        build_application_fraud_payload,
        validate_application_fraud_payload,
    )
    from .sas_client import SasRuntimeResponse, send_message
    from .sas_response import extract_return_fields, summarize_sas_response
except ImportError:
    from alert_log import record_alert
    from application_scenarios import (
        APPLICATION_SCENARIOS,
        ApplicationScenario,
        calculate_30d_counts,
        expected_application_rules,
        normalize_address,
        scenario_history,
    )
    from payloads import (
        build_application_fraud_payload,
        validate_application_fraud_payload,
    )
    from sas_client import SasRuntimeResponse, send_message
    from sas_response import extract_return_fields, summarize_sas_response


ALERT_TYPE_CODE = "app_fraud_app"
ALERT_TYPE_NAME = "Application Fraud Application"
ALERT_ENTITY_TYPE = "sfd_application"
ALERT_ENTITY_PATH = "message.application.identifier"


def select_application_scenario() -> ApplicationScenario:
    st.sidebar.header("Application scenario")
    labels = [scenario.label for scenario in APPLICATION_SCENARIOS]
    selected_label = st.sidebar.selectbox(
        "Scenario", labels, key="application_scenario_selector"
    )
    return next(
        scenario
        for scenario in APPLICATION_SCENARIOS
        if scenario.label == selected_label
    )


def _utc_string(selected_date: date, selected_time: time) -> str:
    return (
        datetime.combine(selected_date, selected_time, tzinfo=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _apply_scenario_flags(scenario: ApplicationScenario) -> None:
    if st.session_state.get("af_loaded_scenario") == scenario.key:
        return
    flags = scenario.verification_flags
    st.session_state["af_disb_owner_match"] = bool(flags["disbAcctOwnerMatchInd"])
    st.session_state["af_income_mismatch"] = bool(flags["incomeMismatchInd"])
    st.session_state["af_employer_unverified"] = bool(flags["employerUnverifiedInd"])
    st.session_state["af_loaded_scenario"] = scenario.key


def _rule_identifiers(response: SasRuntimeResponse) -> list[str]:
    if response.parsed_body is None:
        return []
    summary = summarize_sas_response(response.parsed_body)
    return [
        str(
            rule.get("ruleIdentifier")
            or rule.get("ruleName")
            or rule.get("ruleReference")
            or ""
        )
        for rule in summary.fired_rules
        if isinstance(rule, dict)
    ]


def _record_application_alert(
    *,
    scenario: ApplicationScenario,
    payload: dict[str, Any],
    response: SasRuntimeResponse,
    expected_rules: list[str],
) -> None:
    if response.parsed_body is None:
        return
    summary = summarize_sas_response(response.parsed_body)
    if not summary.alert_created:
        return
    message = payload["message"]
    record_alert(
        {
            "recorded_at": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "fraud_domain": "Application Fraud",
            "schema_name": "Application Fraud",
            "alert_type": ALERT_TYPE_CODE,
            "scenario_key": scenario.key,
            "scenario_label": scenario.label,
            "rule_name": ", ".join(expected_rules),
            "application_identifier": message["application"]["identifier"],
            "customer_identifier": message["customer"]["identifier"],
            "transaction_identifier": message["sas"]["system"]["transactionIdentifier"],
            "expected_alert": bool(expected_rules),
            "actual_alert": summary.alert_created,
            "expected_rules": expected_rules,
            "fired_rules": _rule_identifiers(response),
            # Old readers use this field name.
            "fired_rule_identifiers": _rule_identifiers(response),
            "http_status": response.status_code,
            "outcome_name": summary.outcome_name,
            "alerted_entities": summary.alerted_entities,
        }
    )


def _history_record(payload: dict[str, Any]) -> dict[str, Any]:
    message = payload["message"]
    risk = message["appRisk"]
    return {
        "customerIdentifier": message["customer"]["identifier"],
        "applicationIdentifier": message["application"]["identifier"],
        "eventTime": message["request"]["messageDtTm"],
        "disbAcctNumber": risk["disbAcctNumber"],
        "referencePhone": risk["referencePhone"],
        "normalizedAddress": risk["normalizedAddress"],
        "employerName": message["employment"].get("employerName", ""),
        "salesAgentIdentifier": risk["salesAgentIdentifier"],
    }


def _entity_details(response: SasRuntimeResponse) -> tuple[str, str]:
    if response.parsed_body is None:
        return "", ""
    entities = summarize_sas_response(response.parsed_body).alerted_entities
    if not entities:
        return "", ""
    first = entities[0]
    return (
        str(first.get("outcomeEntityType") or first.get("entityType") or ""),
        str(first.get("outcomeEntity") or first.get("entityIdentifier") or ""),
    )


def _render_application_result(result: dict[str, Any]) -> None:
    response: SasRuntimeResponse = result["response"]
    payload: dict[str, Any] = result["payload"]
    expected_rules: list[str] = result["expected_rules"]
    application_identifier = payload["message"]["application"]["identifier"]
    transaction_identifier = payload["message"]["sas"]["system"][
        "transactionIdentifier"
    ]
    return_fields = (
        extract_return_fields(response.parsed_body)
        if response.parsed_body is not None
        else {"returnType": None, "returnDesc": None, "returnDetails": None}
    )
    summary = (
        summarize_sas_response(response.parsed_body)
        if response.parsed_body is not None
        else None
    )
    actual_alert = summary.alert_created if summary else False
    fired_rules = _rule_identifiers(response)
    comparison_passed = actual_alert == bool(expected_rules) and all(
        rule in fired_rules for rule in expected_rules
    )
    entity_type, entity_identifier = _entity_details(response)
    parsed_message = (
        response.parsed_body.get("message", {})
        if isinstance(response.parsed_body, dict)
        else {}
    )
    parsed_sas = (
        parsed_message.get("sas", {}) if isinstance(parsed_message, dict) else {}
    )
    parsed_system = parsed_sas.get("system", {}) if isinstance(parsed_sas, dict) else {}

    st.subheader("Application Fraud result")
    first, second, third, fourth = st.columns(4)
    first.metric("HTTP Status", response.status_code)
    second.metric("Expected Alert", "Yes" if expected_rules else "No")
    third.metric("Actual Alert", "Yes" if actual_alert else "No")
    fourth.metric("Comparison", "PASS" if comparison_passed else "CHECK")

    st.success(f"Application ID để tìm trong Alert Triage: {application_identifier}")
    overview = {
        "returnType": return_fields.get("returnType"),
        "returnDesc": return_fields.get("returnDesc"),
        "Decision / outcome": (
            summary.outcome_name or summary.outcome if summary else None
        ),
        "Expected Rules": expected_rules,
        "Rules SAS returned": fired_rules,
        "Application ID": application_identifier,
        "Transaction ID": transaction_identifier,
        "Alert entity type": entity_type,
        "Alert entity ID": entity_identifier,
        "Runtime package version": (
            parsed_system.get("packageVersion")
            if isinstance(parsed_system, dict)
            else None
        ),
        "Latency": f"{response.elapsed_ms} ms",
    }
    st.json(overview, expanded=True)
    if return_fields.get("returnDetails") is not None:
        st.caption(f"returnDetails: {return_fields['returnDetails']}")

    triage_url = os.getenv("SAS_ALERT_TRIAGE_URL", "").strip()
    if triage_url:
        st.link_button("Open Alert Triage", triage_url, use_container_width=True)

    st.download_button(
        "Download sent JSON",
        data=json.dumps(payload, ensure_ascii=False, indent=2),
        file_name=f"{application_identifier}.json",
        mime="application/json",
        use_container_width=True,
    )
    response_tab, payload_tab = st.tabs(["Raw response", "Payload JSON"])
    with response_tab:
        if response.parse_error:
            st.error(response.parse_error)
        st.code(response.raw_body, language="text", wrap_lines=True)
    with payload_tab:
        st.json(payload, expanded=False)


def render_application_console(
    scenario: ApplicationScenario,
    *,
    endpoint: str,
    timeout_seconds: float,
    verify_tls: bool,
    ca_bundle: str | None,
    render_response: Callable[[SasRuntimeResponse, str], None] | None = None,
) -> None:
    """Render one Application Fraud form inside the existing Streamlit app."""

    del render_response  # The domain-specific result view is rendered below.
    _apply_scenario_flags(scenario)
    st.subheader(scenario.label)
    st.caption(scenario.description)
    st.info(
        f"Alert contract: {ALERT_TYPE_NAME} (`{ALERT_TYPE_CODE}`), "
        f"entity `{ALERT_ENTITY_TYPE}` at `{ALERT_ENTITY_PATH}`."
    )

    history_mode = st.radio(
        "30-day history source",
        ["Scenario history", "Session history"],
        horizontal=True,
        key="af_history_mode",
        help=(
            "Scenario history builds stable synthetic preconditions. Session history uses "
            "only applications successfully posted during this Streamlit session."
        ),
    )
    session_history: list[dict[str, Any]] = st.session_state.setdefault(
        "af_session_history", []
    )
    if history_mode == "Session history" and st.button(
        "Clear session history", key="af_clear_history", use_container_width=True
    ):
        session_history.clear()
        st.rerun()

    now = datetime.now(timezone.utc).replace(microsecond=0)
    tabs = st.tabs(
        [
            "Application",
            "Applicant & Customer",
            "Employment & Financial",
            "Origination & Device",
            "CIC & Verification",
        ]
    )
    with tabs[0]:
        first, second = st.columns(2)
        application_type = first.selectbox(
            "Loan product", ["PERSONAL_LOAN", "HOME_LOAN", "AUTO_LOAN"]
        )
        application_purpose = second.selectbox(
            "Purpose", ["HOME_RENOVATION", "PERSONAL_USE", "VEHICLE_PURCHASE"]
        )
        application_amount = first.number_input(
            "Amount", min_value=0.0, value=50_000_000.0, step=1_000_000.0
        )
        currency_code = second.selectbox("Currency", ["VND", "USD"])
        application_channel = first.selectbox(
            "Channel", ["WEB", "MOBILE", "BRANCH", "PARTNER"]
        )
        application_status = second.selectbox(
            "Status", ["SUBMITTED", "PENDING", "APPROVED"]
        )
        application_stage = first.selectbox(
            "Stage", ["UNDER_REVIEW", "DOCUMENT_CHECK", "DECISION"]
        )
        event_date = second.date_input("Event date (UTC)", value=now.date())
        event_time = first.time_input("Event time (UTC)", value=now.time())
        message_datetime = _utc_string(event_date, event_time)
        st.caption(
            "Application ID and SAS transaction ID are generated afresh on every send."
        )

    with tabs[1]:
        first, second = st.columns(2)
        customer_identifier = first.text_input(
            "Customer ID", "CUST-41127322", key="af_customer_identifier"
        )
        applicant_identifier = second.text_input(
            "Applicant ID", "APL-BANKA-0001", key="af_applicant_identifier"
        )
        applicant_name = first.text_input("Applicant name", "Nguyen Van Demo")
        customer_name = second.text_input("Customer name", "Nguyen Van Demo")
        customer_type = first.selectbox("Customer type", ["INDIVIDUAL", "BUSINESS"])
        identification_number = second.text_input(
            "CCCD / Identification number", "079099009999"
        )
        address_country_code = first.text_input("Address country", "VN", max_chars=3)
        email = second.text_input("Email", "demo.application@example.com")
        phone = first.text_input("Phone", "+84901234567")
        address = second.text_input("Address", "88 Cộng Hòa, TP. HCM")
        months_at_location = first.number_input(
            "Months at location", min_value=0, value=24, step=1
        )
        normalized_address = normalize_address(address)
        st.code(f"Normalized address: {normalized_address}", language="text")

    with tabs[2]:
        first, second = st.columns(2)
        employer_name = first.text_input("Employer name", "Demo Company")
        employment_status = second.selectbox(
            "Employment status", ["EMPLOYED", "SELF_EMPLOYED", "UNEMPLOYED"]
        )
        monthly_regular_income = first.number_input(
            "Monthly income", min_value=0.0, value=25_000_000.0, step=1_000_000.0
        )
        outstanding_debt = second.number_input(
            "Outstanding debt", min_value=0.0, value=5_000_000.0, step=1_000_000.0
        )

    with tabs[3]:
        first, second = st.columns(2)
        bank_id = first.text_input("Bank ID", "BANK-A")
        sales_agent_identifier = second.text_input("Sales Agent ID", "SALES-001")
        disb_account_number = first.text_input("Disbursement account", "9704000012345")
        reference_phone = second.text_input("Reference phone", "0912345678")
        device_identifier = first.text_input("Device ID", "DEV-APP-0001")
        device_ip_address = second.text_input("IP address", "203.0.113.42")
        sales_agent_app_count = first.number_input(
            "Sales agent applications (30d)", min_value=0, value=1, step=1
        )
        sales_agent_risk_rate = second.number_input(
            "Sales agent risk rate (30d)", min_value=0.0, value=0.0, step=0.01
        )
        sales_agent_location_risk = first.checkbox(
            "Sales agent location risk", value=False
        )
        identity_mismatch = second.checkbox("Identity mismatch", value=False)

    with tabs[4]:
        first, second = st.columns(2)
        cic_inquiry_count_7_days = first.number_input(
            "CIC inquiry count 7 days", min_value=0, value=0, step=1
        )
        cic_inquiry_count_30_days = second.number_input(
            "CIC inquiry count 30 days", min_value=0, value=0, step=1
        )
        disb_owner_match = first.checkbox(
            "Account owner matches applicant?", key="af_disb_owner_match"
        )
        income_mismatch = second.checkbox("Income mismatch?", key="af_income_mismatch")
        employer_unverified = first.checkbox(
            "Employer unverified?", key="af_employer_unverified"
        )
        st.caption(
            "Verification flags are synthetic POC inputs; no real verification service is connected."
        )

    as_of = datetime.fromisoformat(message_datetime.replace("Z", "+00:00"))
    current = {
        "customerIdentifier": customer_identifier,
        "disbAcctNumber": disb_account_number,
        "referencePhone": reference_phone,
        "normalizedAddress": normalized_address,
        "employerName": employer_name,
        "salesAgentIdentifier": sales_agent_identifier,
    }
    history = (
        scenario_history(scenario, current=current, as_of=as_of)
        if history_mode == "Scenario history"
        else session_history
    )
    counts = calculate_30d_counts(current, history, as_of=as_of)
    app_risk: dict[str, Any] = {
        "bankId": bank_id,
        "salesAgentIdentifier": sales_agent_identifier,
        "disbAcctNumber": disb_account_number,
        "referencePhone": reference_phone,
        "normalizedAddress": normalized_address,
        "disbAcctOwnerMatchInd": int(disb_owner_match),
        **counts,
        "employerUnverifiedInd": int(employer_unverified),
        "incomeMismatchInd": int(income_mismatch),
        "salesAgentAppCnt30d": int(sales_agent_app_count),
        "salesAgentRiskRate30d": float(sales_agent_risk_rate),
        "salesAgentLocRiskInd": int(sales_agent_location_risk),
        "identityMismatchInd": int(identity_mismatch),
    }
    expected_rules = expected_application_rules(app_risk)
    scenario_exact = tuple(expected_rules) == scenario.expected_rules

    st.subheader("Derived 30-day context")
    count_columns = st.columns(4)
    for column, field_name in zip(count_columns, counts):
        column.metric(field_name, counts[field_name])
    st.caption(
        "Current application is included. Streamlit/upstream calculates these distinct-customer "
        "features and sends the snapshot in message.appRisk."
    )
    first, second, third = st.columns(3)
    first.metric("Expected Alert", "Yes" if expected_rules else "No")
    second.metric("Expected Rules", len(expected_rules))
    third.metric("Scenario isolation", "PASS" if scenario_exact else "CHECK")
    st.code("\n".join(expected_rules) or "No Decision Rule expected", language="text")

    preview_values = {
        "message_datetime": message_datetime,
        "application_type": application_type,
        "application_amount": application_amount,
        "currency_code": currency_code,
        "application_channel": application_channel,
        "application_purpose": application_purpose,
        "application_status": application_status,
        "application_stage": application_stage,
        "applicant_identifier": applicant_identifier,
        "applicant_name": applicant_name,
        "monthly_regular_income": monthly_regular_income,
        "outstanding_debt": outstanding_debt,
        "customer_identifier": customer_identifier,
        "customer_name": customer_name,
        "customer_type": customer_type,
        "address_country_code": address_country_code.upper(),
        "identification_number": identification_number,
        "email": email,
        "phone": phone,
        "employer_name": employer_name,
        "employment_status": employment_status,
        "months_at_location": months_at_location,
        "device_identifier": device_identifier,
        "device_ip_address": device_ip_address,
        "cic_inquiry_count_7_days": cic_inquiry_count_7_days,
        "cic_inquiry_count_30_days": cic_inquiry_count_30_days,
        "app_risk": app_risk,
    }
    preview_payload = build_application_fraud_payload(preview_values)
    validation_errors = validate_application_fraud_payload(preview_payload)
    st.subheader("Payload preview")
    st.code(
        "Application ID: " + preview_payload["message"]["application"]["identifier"],
        language="text",
    )
    st.json(preview_payload, expanded=False)
    for error in validation_errors:
        st.error(error)

    if st.button(
        "Send Application Fraud to SAS",
        type="primary",
        disabled=bool(validation_errors),
        use_container_width=True,
    ):
        try:
            # A Streamlit button click starts a new run, so this preview has fresh IDs.
            # Sending the same object keeps the visible Application ID and sent JSON aligned.
            payload_to_send = preview_payload
            send_errors = validate_application_fraud_payload(payload_to_send)
            if send_errors:
                raise ValueError(" | ".join(send_errors))
            with st.spinner("Waiting for SAS runtime..."):
                response = send_message(
                    endpoint=endpoint,
                    payload=payload_to_send,
                    timeout_seconds=timeout_seconds,
                    verify_tls=verify_tls,
                    ca_bundle=ca_bundle,
                )
            if 200 <= response.status_code < 300:
                session_history.append(_history_record(payload_to_send))
            _record_application_alert(
                scenario=scenario,
                payload=payload_to_send,
                response=response,
                expected_rules=expected_rules,
            )
            st.session_state["latest_application_result"] = {
                "response": response,
                "payload": payload_to_send,
                "expected_rules": expected_rules,
            }
        except requests.RequestException as error:
            st.error(f"Could not reach SAS runtime: {error}")
        except ValueError as error:
            st.error(str(error))

    latest_result = st.session_state.get("latest_application_result")
    if latest_result:
        _render_application_result(latest_result)

    with st.expander("Application session history"):
        st.dataframe(session_history, use_container_width=True, hide_index=True)
