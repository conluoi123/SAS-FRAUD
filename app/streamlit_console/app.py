"""SAS Fraud Decisioning multi-scenario test console."""

from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, time, timezone
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

try:
    from .payloads import build_payment_fraud_payload
    from .sas_client import SasRuntimeResponse, send_message
    from .sas_response import summarize_sas_response
    from .scenarios import STATUS_LABEL, families, scenarios_in_family
except ImportError:
    # Streamlit executes this file as a script when launched from this directory.
    from payloads import build_payment_fraud_payload
    from sas_client import SasRuntimeResponse, send_message
    from sas_response import summarize_sas_response
    from scenarios import STATUS_LABEL, families, scenarios_in_family


load_dotenv()

DEFAULT_ENDPOINT = os.getenv(
    "SAS_DECISION_URL",
    "https://banking-fraud.ingress-nginx.sas.env/detection/decision/execute",
)


def _utc_string(selected_date: date, selected_time: time) -> str:
    value = datetime.combine(selected_date, selected_time, tzinfo=timezone.utc)
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _new_transaction_id(customer_identifier: str) -> str:
    suffix = uuid.uuid4().hex[:8].upper()
    return f"TXN-{customer_identifier}-{suffix}"


def _response_package_version(parsed_body: dict[str, Any]) -> Any:
    message = parsed_body.get("message", {})
    sas = message.get("sas", {}) if isinstance(message, dict) else {}
    system = sas.get("system", {}) if isinstance(sas, dict) else {}
    return system.get("packageVersion") if isinstance(system, dict) else None


def _render_response(
    response: SasRuntimeResponse, expected_package_version: str = ""
) -> None:
    st.subheader("SAS response")
    status_column, duration_column, service_column = st.columns(3)
    status_column.metric("HTTP status", response.status_code)
    duration_column.metric("Round trip", f"{response.elapsed_ms} ms")
    service_column.metric(
        "SAS response",
        response.headers.get("sas-service-response-flag", "unknown"),
    )

    if response.parsed_body is None:
        st.error("SAS returned a body that could not be parsed.")
        if response.parse_error:
            st.caption(response.parse_error)
    else:
        summary = summarize_sas_response(response.parsed_body)
        package_version = _response_package_version(response.parsed_body)
        decision_column, alert_column, rules_column, total_column = st.columns(4)
        decision_column.metric("Decision", summary.outcome_name or "No outcome")
        alert_column.metric("Alert", "Created" if summary.alert_created else "No alert")
        rules_column.metric(
            "Rules fired", f"{len(summary.fired_rules)}/{summary.evaluated_rule_count}"
        )
        total_column.metric("SAS total", f"{summary.timings.get('total', '-')} ms")

        if expected_package_version:
            actual = str(package_version or "")
            if actual == expected_package_version.strip():
                st.success(f"Runtime package matches expected version {actual}.")
            else:
                st.error(
                    "Runtime package mismatch: "
                    f"expected {expected_package_version.strip()}, got {actual or 'unknown'}."
                )
        elif package_version is not None:
            st.info(f"Runtime packageVersion: {package_version}")

        st.caption(
            " | ".join(
                filter(
                    None,
                    [
                        f"Message: {summary.message_identifier}"
                        if summary.message_identifier
                        else None,
                        f"Transaction: {summary.transaction_identifier}"
                        if summary.transaction_identifier
                        else None,
                        f"Decision reference: {summary.reference_identifier}"
                        if summary.reference_identifier
                        else None,
                    ],
                )
            )
        )

        if summary.fired_rules:
            st.markdown("#### Fired rules")
            st.dataframe(summary.fired_rules, use_container_width=True, hide_index=True)

        if summary.alerted_entities:
            st.markdown("#### Alerted entities")
            st.dataframe(summary.alerted_entities, use_container_width=True, hide_index=True)

        parsed_tab, profiles_tab, timings_tab = st.tabs(
            ["Parsed response", "Profiles", "Timings"]
        )
        with parsed_tab:
            st.json(response.parsed_body, expanded=False)
        with profiles_tab:
            profiles = (
                response.parsed_body.get("profiles", {})
                if isinstance(response.parsed_body, dict)
                else {}
            )
            st.json(profiles, expanded=False)
        with timings_tab:
            st.json(summary.timings)

    with st.expander("Raw response and headers"):
        st.json(response.headers)
        st.code(response.raw_body, language="text", wrap_lines=True)


def _select_scenario():
    st.sidebar.header("Scenario")
    family = st.sidebar.selectbox("Rule family", families())
    family_scenarios = scenarios_in_family(family)
    labels = [s.label for s in family_scenarios]
    chosen_label = st.sidebar.selectbox("Scenario", labels)
    scenario = next(s for s in family_scenarios if s.label == chosen_label)

    badge = {
        "built": "🟢",
        "prototype": "🟡",
        "draft-blocked": "🔴",
    }[scenario.status]
    st.sidebar.caption(f"{badge} {STATUS_LABEL[scenario.status]}")
    st.sidebar.caption(f"Spec: `{scenario.spec_doc}`")
    return scenario


def _form_values(scenario) -> dict[str, Any]:
    st.subheader(scenario.label)
    st.caption(scenario.description)
    if scenario.status == "draft-blocked":
        st.warning(
            "Kịch bản này chưa deploy được trên SAS — còn phụ thuộc xác nhận kiến trúc/"
            f"dữ liệu, xem `{scenario.spec_doc}`. Payload dưới đây chỉ để chuẩn bị sẵn "
            "hình dạng test, gửi thử có thể không fire đúng như mô tả."
        )

    preset = {
        "amount": 750.0,
        "device_identifier": "DEV-NEW-9001",
        "device_fingerprint": "FP-NEW-9001",
        "auth_decision": "DENY",
        "auth_level": "LOW",
        "ecommerce_authentication": "FAILED",
    }

    tab_names = ["Routing", "Entities", "Amounts", "Device", "Authentication", "Merchant"]
    extra_tab_titles = {
        "device_known": "Known devices",
        "subscription": "Subscription",
        "structuring": "Structuring",
        "device_network": "Device network (preview)",
        "session": "Session/Login (preview)",
        "chargeback": "Chargeback",
    }
    for tab_key in scenario.extra_tabs:
        tab_names.append(extra_tab_titles[tab_key])

    tabs = st.tabs(tab_names)
    tab_by_name = dict(zip(tab_names, tabs))

    with tab_by_name["Routing"]:
        first, second = st.columns(2)
        origination_type = first.selectbox("Origination type", ["DC", "CC"])
        activity_type = second.text_input("Activity type", value="CA", max_chars=8)
        authentication_type = first.selectbox(
            "Authentication type", ["CVV", "3DS", "PIN", "BIOMETRIC", "NONE"]
        )
        channel_type = second.selectbox("Channel type", ["WEB", "MOBILE", "ATM", "POS"])
        customer_type = first.selectbox("Customer type", ["INDIVIDUAL", "BUSINESS"])
        selected_date = second.date_input("Message date (UTC)", value=date(2026, 6, 5))
        selected_time = first.time_input("Message time (UTC)", value=time(2, 20))

    with tab_by_name["Entities"]:
        first, second = st.columns(2)
        customer_identifier = first.text_input("Customer identifier", "CUST-41127322")
        customer_surname = second.text_input("Customer surname", "Carlyle")
        customer_country = first.text_input("Customer country", "US", max_chars=3)
        credit_card_number = second.text_input("Credit card number", "4111111111111114")
        cardholder_country = first.text_input("Cardholder country", "US", max_chars=3)
        debit_account_number = second.text_input(
            "Debit account number", "DA-CUST-41127322"
        )
        debit_card_number = second.text_input("Debit card number / profile key", "DC-41127322")
        transaction_identifier = st.text_input(
            "Transaction identifier",
            value=_new_transaction_id(customer_identifier),
            help="Use a new identifier when repeating a test to avoid duplicate behavior.",
        )

    with tab_by_name["Amounts"]:
        first, second = st.columns(2)
        transaction_amount = first.number_input(
            "Transaction amount", min_value=0.0, value=700.0, step=10.0
        )
        card_amount = second.number_input(
            "Card financial amount", min_value=0.0, value=preset["amount"], step=10.0
        )
        usd_amount = first.number_input(
            "USD amount", min_value=0.0, value=500.0, step=10.0
        )
        credit_card_limit = second.number_input(
            "Credit card limit", min_value=0.0, value=5000.0, step=100.0
        )
        currency_code = first.text_input("Currency", "USD", max_chars=3)
        card_present_ind = second.selectbox(
            "Card present indicator",
            ["1", "0"],
            help="In the current SAS sample rules, '1' means Card Not Present.",
        )
        customer_present_ind = first.selectbox("Customer present indicator", ["1", "0"])

    with tab_by_name["Device"]:
        first, second = st.columns(2)
        device_identifier = first.text_input(
            "Device identifier", preset["device_identifier"], max_chars=100
        )
        device_fingerprint = second.text_input(
            "Device fingerprint[1] (sent for reference)",
            preset["device_fingerprint"],
            max_chars=100,
        )
        device_fingerprint_type = first.text_input(
            "Device fingerprint type[1]", "SAS", max_chars=25
        )
        device_ip_address = second.text_input("Device IP address", "203.0.113.42")

    known_device_1 = known_device_2 = known_device_3 = ""
    if "device_known" in scenario.extra_tabs:
        with tab_by_name["Known devices"]:
            st.caption(
                "Các giá trị này KHÔNG được gửi lên SAS — chỉ dùng để hiển thị đúng "
                "'Rule Readiness' bên dưới, giả định đây là 3 thiết bị đã seed vào "
                "profile qua các lần gửi trước."
            )
            known_first, known_second, known_third = st.columns(3)
            known_device_1 = known_first.text_input("knownDeviceFingerprint[1]", "DEV-KNOWN-001")
            known_device_2 = known_second.text_input("knownDeviceFingerprint[2]", "DEV-KNOWN-002")
            known_device_3 = known_third.text_input("knownDeviceFingerprint[3]", "DEV-KNOWN-003")

    with tab_by_name["Authentication"]:
        first, second = st.columns(2)
        auth_decision = first.selectbox(
            "Authentication decision",
            ["DENY", "CHALLENGE", "ACCEPT"],
            index=["DENY", "CHALLENGE", "ACCEPT"].index(preset["auth_decision"]),
        )
        auth_level = second.selectbox(
            "Authentication level",
            ["LOW", "MEDIUM", "HIGH"],
            index=["LOW", "MEDIUM", "HIGH"].index(preset["auth_level"]),
        )
        auth_result = first.selectbox(
            "Authentication result[1]", ["FAILURE", "EXPIRED", "SUCCESS"]
        )
        auth_type = second.selectbox(
            "Authentication type", ["3DS_V2", "OTP_SMS", "FIDO", "NONE"]
        )
        ecommerce_authentication = first.selectbox(
            "E-commerce authentication",
            ["FAILED", "ATTEMPTED", "SUCCESS"],
            index=["FAILED", "ATTEMPTED", "SUCCESS"].index(
                preset["ecommerce_authentication"]
            ),
        )

    with tab_by_name["Merchant"]:
        first, second = st.columns(2)
        merchant_name = first.text_input("Merchant name", "ECOM DIGITAL STORE")
        merchant_category_code = second.text_input("Merchant category code", "5732")
        merchant_country = first.text_input("Merchant country", "US", max_chars=3)

    subscription_identifier = ""
    if "subscription" in scenario.extra_tabs:
        with tab_by_name["Subscription"]:
            st.caption(
                "Để rule 3 fire cần gửi >=3 message trong <30 phút, mỗi lần đổi "
                "'Subscription identifier' sang giá trị khác và giữ ecommerceAuthentication "
                "ở tab Authentication = FAILED hoặc ATTEMPTED."
            )
            subscription_identifier = st.text_input(
                "Subscription identifier", "SUB-STREAM-APP-001", max_chars=26
            )

    structuring_reference_threshold = 500.0
    if "structuring" in scenario.extra_tabs:
        with tab_by_name["Structuring"]:
            st.caption(
                "Ngưỡng tham chiếu bên dưới KHÔNG được gửi lên SAS — chỉ dùng để tính "
                "gợi ý 'Rule Readiness'. Ngưỡng thật đang hardcode trong rule là 500 "
                "(xem docs/rules/rule_04_structuring_threshold_split.md), sửa cho khớp "
                "khi có ngưỡng thật từ business."
            )
            structuring_reference_threshold = st.number_input(
                "Ngưỡng kiểm soát tham chiếu", min_value=0.0, value=500.0, step=10.0
            )
            st.caption(
                "Để rule fire cần gửi >=2 giao dịch trong ngưỡng [80%, 100%) trong 1 giờ, "
                "với tổng vượt ngưỡng — gửi nhiều message liên tiếp đổi 'Card financial "
                "amount' ở tab Amounts."
            )

    if "device_network" in scenario.extra_tabs:
        with tab_by_name["Device network (preview)"]:
            st.info(
                "Chưa có field bổ sung — kịch bản này cần một Profile Variable Set mới "
                "keyed theo device.identifier, chưa xác nhận SAS hỗ trợ. Dùng tab Device "
                "ở trên để chuẩn bị giá trị, xem docs/rules/rule_05_device_fanout_DRAFT.md."
            )

    ip_country_code = ""
    if "session" in scenario.extra_tabs:
        with tab_by_name["Session/Login (preview)"]:
            st.caption(
                "Preview field — chưa xác nhận SAS nhận message login/session riêng, xem "
                "docs/rules/rule_06_login_impossible_travel_DRAFT.md."
            )
            ip_country_code = st.text_input("digital.ipCountryCode (session)", "VN", max_chars=3)

    chargeback_reference_number = ""
    chargeback_identifier = ""
    chargeback_amount = 0.0
    chargeback_payment_method = ""
    chargeback_purchase_dttm = ""
    chargeback_misc_data = ""
    if "chargeback" in scenario.extra_tabs:
        with tab_by_name["Chargeback"]:
            st.caption(
                "Routing (activityType = CB ở tab Routing) đang là giả định, chưa xác nhận "
                "trên SAS — xem docs/rules/rule_07_refund_chargeback_abuse.md. Để rule fire "
                "cần gửi >=3 message chargeback cho cùng debit card trong 90 ngày."
            )
            first, second = st.columns(2)
            chargeback_reference_number = first.text_input(
                "Reference number (giao dịch gốc)", "REF-0001", max_chars=30
            )
            chargeback_identifier = second.text_input(
                "Payment ID (giao dịch gốc)", "PMT-0001", max_chars=100
            )
            chargeback_amount = first.number_input(
                "Chargeback amount (giao dịch gốc)", min_value=0.0, value=750.0, step=10.0
            )
            chargeback_payment_method = second.text_input(
                "Payment method (giao dịch gốc)", "1", max_chars=1
            )
            chargeback_purchase_dttm = first.text_input(
                "purchaseDtTm (giao dịch gốc, ISO 8601)", "2026-05-01T10:00:00Z"
            )
            chargeback_misc_data = second.text_input("Miscellaneous data", "", max_chars=100)

    return {
        "origination_type": origination_type,
        "activity_type": activity_type,
        "authentication_type": authentication_type,
        "channel_type": channel_type,
        "customer_type": customer_type,
        "message_classification": "GLOBAL",
        "message_datetime": _utc_string(selected_date, selected_time),
        "customer_identifier": customer_identifier,
        "customer_surname": customer_surname,
        "customer_country": customer_country.upper(),
        "credit_card_number": credit_card_number,
        "credit_card_limit": credit_card_limit,
        "cardholder_country": cardholder_country.upper(),
        "debit_account_number": debit_account_number,
        "debit_card_number": debit_card_number,
        "transaction_identifier": transaction_identifier,
        "transaction_amount": transaction_amount,
        "card_amount": card_amount,
        "usd_amount": usd_amount,
        "currency_code": currency_code.upper(),
        "card_present_ind": card_present_ind,
        "customer_present_ind": customer_present_ind,
        "device_identifier": device_identifier,
        "device_fingerprint": device_fingerprint,
        "device_fingerprint_type": device_fingerprint_type,
        "device_ip_address": device_ip_address,
        "known_device_1": known_device_1,
        "known_device_2": known_device_2,
        "known_device_3": known_device_3,
        "auth_decision": auth_decision,
        "auth_level": auth_level,
        "auth_result": auth_result,
        "auth_type": auth_type,
        "ecommerce_authentication": ecommerce_authentication,
        "merchant_name": merchant_name,
        "merchant_category_code": merchant_category_code,
        "merchant_country": merchant_country.upper(),
        "subscription_identifier": subscription_identifier,
        "structuring_reference_threshold": structuring_reference_threshold,
        "ip_country_code": ip_country_code.upper() if ip_country_code else "",
        "chargeback_reference_number": chargeback_reference_number,
        "chargeback_identifier": chargeback_identifier,
        "chargeback_amount": chargeback_amount,
        "chargeback_payment_method": chargeback_payment_method,
        "chargeback_purchase_dttm": chargeback_purchase_dttm,
        "chargeback_misc_data": chargeback_misc_data,
    }


def main() -> None:
    st.set_page_config(page_title="SAS Fraud Console", page_icon="S", layout="wide")
    st.title("SAS Fraud Decisioning Test Console")
    st.caption(
        "Chọn 1 scenario ở sidebar, chỉnh field cần thiết, gửi message tới SAS và xem "
        "quyết định trả về."
    )

    scenario = _select_scenario()

    with st.sidebar:
        st.divider()
        st.header("Runtime")
        endpoint = st.text_input("Decision endpoint", value=DEFAULT_ENDPOINT)
        timeout_seconds = st.number_input(
            "Timeout (seconds)", min_value=1, max_value=300, value=int(os.getenv("SAS_REQUEST_TIMEOUT_SECONDS", "30"))
        )
        verify_default = os.getenv("SAS_TLS_VERIFY", "false").lower() == "true"
        verify_tls = st.toggle("Verify TLS certificate", value=verify_default)
        ca_bundle = st.text_input("CA bundle path", value=os.getenv("SAS_CA_BUNDLE", ""))
        expected_package_version = st.text_input(
            "Expected package version",
            value=os.getenv("SAS_EXPECTED_PACKAGE_VERSION", ""),
            placeholder="50026",
            help="Optional. The app will warn if SAS returns a different message.sas.system.packageVersion.",
        )
        if not verify_tls:
            st.warning("TLS verification is disabled for this test environment.")
        st.divider()
        st.markdown("**Target rule**")
        st.code(f"{scenario.rule_name}\n{scenario.rule_reason}", language="text")
        st.markdown("**Routing**")
        st.code("SAS Debit Card Fraud\nPayment Fraud\nGLOBAL", language="text")

    values = _form_values(scenario)
    payload = build_payment_fraud_payload(values)

    st.subheader("Rule Readiness")
    checks = scenario.checks(values)
    passed = sum(1 for check in checks if check["Pass"])
    first, second, third = st.columns(3)
    first.metric("Expected rule", scenario.rule_name)
    second.metric("Conditions met", f"{passed}/{len(checks)}")
    third.metric(
        "Expected action",
        scenario.default_action if passed == len(checks) else "No hit",
    )
    st.dataframe(checks, use_container_width=True, hide_index=True)

    st.subheader("Payload")
    mode = st.segmented_control("Edit mode", ["Form payload", "Raw JSON"], default="Form payload")
    raw_payload = st.text_area(
        "JSON sent to SAS",
        value=json.dumps(payload, indent=2),
        height=420,
        disabled=mode == "Form payload",
        label_visibility="collapsed",
    )

    payload_to_send = payload
    validation_error = None
    if mode == "Raw JSON":
        try:
            payload_to_send = json.loads(raw_payload)
            if not isinstance(payload_to_send, dict) or "message" not in payload_to_send:
                validation_error = "The root object must contain 'message'."
        except json.JSONDecodeError as error:
            validation_error = f"Invalid JSON: {error}"

    if validation_error:
        st.error(validation_error)

    if st.button(
        "Send to SAS",
        type="primary",
        icon=":material/send:",
        disabled=validation_error is not None,
        use_container_width=True,
    ):
        try:
            with st.spinner("Waiting for SAS runtime..."):
                response = send_message(
                    endpoint=endpoint,
                    payload=payload_to_send,
                    timeout_seconds=float(timeout_seconds),
                    verify_tls=verify_tls,
                    ca_bundle=ca_bundle or None,
                )
            st.session_state["latest_sas_response"] = response
        except requests.RequestException as error:
            st.error(f"Could not reach SAS runtime: {error}")
        except ValueError as error:
            st.error(str(error))

    latest_response = st.session_state.get("latest_sas_response")
    if latest_response:
        _render_response(latest_response, expected_package_version)


if __name__ == "__main__":
    main()
