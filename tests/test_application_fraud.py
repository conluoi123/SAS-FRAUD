from __future__ import annotations

import json
from datetime import datetime, timezone

from app.streamlit_console import alert_log
from app.streamlit_console.application_scenarios import (
    APPLICATION_SCENARIOS,
    calculate_30d_counts,
    expected_application_rules,
    normalize_address,
    scenario_history,
)
from app.streamlit_console.payloads import (
    build_application_fraud_payload,
    validate_application_fraud_payload,
)


BASE_RISK = {
    "bankId": "BANK-A",
    "salesAgentIdentifier": "SALES-001",
    "disbAcctNumber": "9704000012345",
    "referencePhone": "0912345678",
    "normalizedAddress": "88 CONG HOA TP HCM",
    "disbAcctOwnerMatchInd": 1,
    "disbAcctCustCnt30d": 1,
    "refPhoneCustCnt30d": 1,
    "employerUnverifiedInd": 0,
    "incomeMismatchInd": 0,
    "addressCustCnt30d": 1,
    "clusterCustCnt30d": 1,
    "salesAgentAppCnt30d": 1,
    "salesAgentRiskRate30d": 0.0,
    "salesAgentLocRiskInd": 0,
    "identityMismatchInd": 0,
}

BASE_VALUES = {
    "message_datetime": "2026-09-04T08:00:00Z",
    "application_type": "PERSONAL_LOAN",
    "application_amount": 50_000_000.0,
    "currency_code": "VND",
    "application_channel": "WEB",
    "application_purpose": "HOME_RENOVATION",
    "application_status": "SUBMITTED",
    "application_stage": "UNDER_REVIEW",
    "applicant_identifier": "APL-BANKA-0001",
    "applicant_name": "Nguyen Van Demo",
    "monthly_regular_income": 25_000_000.0,
    "outstanding_debt": 5_000_000.0,
    "customer_identifier": "CUST-41127322",
    "customer_name": "Nguyen Van Demo",
    "customer_type": "INDIVIDUAL",
    "address_country_code": "VN",
    "identification_number": "079099009999",
    "email": "demo.application@example.com",
    "phone": "+84901234567",
    "employer_name": "Demo Company",
    "employment_status": "EMPLOYED",
    "months_at_location": 24,
    "device_identifier": "DEV-APP-0001",
    "device_ip_address": "203.0.113.42",
    "cic_inquiry_count_7_days": 0,
    "cic_inquiry_count_30_days": 0,
    "app_risk": BASE_RISK,
}


def test_application_payload_matches_contract_and_keeps_zero_values() -> None:
    payload = build_application_fraud_payload(BASE_VALUES)
    message = payload["message"]

    assert message["request"]["schemaName"] == "Application Fraud"
    assert message["request"]["messageClassificationName"] == "GLOBAL"
    assert "solution" not in message
    assert message["application"]["identifier"].startswith("APP-20260904-")
    assert message["customer"]["identifier"] == "CUST-41127322"
    assert message["applicant"]["identifier"] == "APL-BANKA-0001"
    assert message["identification"]["number"] == "079099009999"
    assert message["applicant"]["monthlyRegularIncome"] == 25_000_000.0
    assert message["employment"]["employerName"] == "Demo Company"
    assert message["device"]["ipAddress"] == "203.0.113.42"
    assert message["cic"] == {"inquiryCount7Days": 0, "inquiryCount30Days": 0}
    assert message["appRisk"]["incomeMismatchInd"] == 0
    assert message["appRisk"]["salesAgentRiskRate30d"] == 0.0
    assert validate_application_fraud_payload(payload) == []


def test_builder_generates_fresh_application_and_transaction_ids() -> None:
    first = build_application_fraud_payload(BASE_VALUES)["message"]
    second = build_application_fraud_payload(BASE_VALUES)["message"]

    assert first["application"]["identifier"] != second["application"]["identifier"]
    assert (
        first["sas"]["system"]["transactionIdentifier"]
        != second["sas"]["system"]["transactionIdentifier"]
    )
    assert (
        first["application"]["identifier"]
        != first["sas"]["system"]["transactionIdentifier"]
    )


def test_normalize_vietnamese_address() -> None:
    assert (
        normalize_address(" 88 Đường Cộng-Hòa, TP. HCM ") == "88 DUONG CONG HOA TP HCM"
    )


def test_each_scenario_matches_only_its_expected_rule() -> None:
    as_of = datetime(2026, 9, 4, 8, tzinfo=timezone.utc)
    current = {
        "customerIdentifier": "CUST-CURRENT",
        "disbAcctNumber": BASE_RISK["disbAcctNumber"],
        "referencePhone": BASE_RISK["referencePhone"],
        "normalizedAddress": BASE_RISK["normalizedAddress"],
        "employerName": "Demo Company",
        "salesAgentIdentifier": BASE_RISK["salesAgentIdentifier"],
    }

    for scenario in APPLICATION_SCENARIOS:
        history = scenario_history(scenario, current=current, as_of=as_of)
        counts = calculate_30d_counts(current, history, as_of=as_of)
        risk = {
            **BASE_RISK,
            **counts,
            **scenario.verification_flags,
        }
        assert expected_application_rules(risk) == list(scenario.expected_rules)


def test_scenario_counts_include_the_current_application() -> None:
    as_of = datetime(2026, 9, 4, 8, tzinfo=timezone.utc)
    current = {
        "customerIdentifier": "CUST-CURRENT",
        "disbAcctNumber": BASE_RISK["disbAcctNumber"],
        "referencePhone": BASE_RISK["referencePhone"],
        "normalizedAddress": BASE_RISK["normalizedAddress"],
        "employerName": "Demo Company",
        "salesAgentIdentifier": BASE_RISK["salesAgentIdentifier"],
    }
    expected_counts = {
        "normal": (1, 1, 1, 1),
        "shared_disbursement_account": (2, 1, 2, 2),
        "shared_reference_network": (1, 3, 3, 3),
        "income_employer_inconsistency": (1, 1, 1, 1),
        "linked_high_density_address": (2, 1, 4, 4),
    }
    for scenario in APPLICATION_SCENARIOS:
        counts = calculate_30d_counts(
            current,
            scenario_history(scenario, current=current, as_of=as_of),
            as_of=as_of,
        )
        assert tuple(counts.values()) == expected_counts[scenario.key]


def test_validator_rejects_negative_amount_and_solution() -> None:
    payload = build_application_fraud_payload(
        {**BASE_VALUES, "application_amount": -1.0}
    )
    payload["message"]["solution"] = {"channelType": "WEB"}

    errors = validate_application_fraud_payload(payload)

    assert any("application.amount must not be negative" in error for error in errors)
    assert any("must not contain message.solution" in error for error in errors)


def test_old_alert_log_remains_readable(tmp_path, monkeypatch) -> None:
    old_entries = [
        {
            "recorded_at": "2026-06-05T02:20:00Z",
            "scenario_label": "Old Payment scenario",
            "transaction_identifier": "TXN-OLD",
        }
    ]
    log_path = tmp_path / ".alert_log.json"
    log_path.write_text(json.dumps(old_entries), encoding="utf-8")
    monkeypatch.setattr(alert_log, "LOG_FILE", log_path)

    assert alert_log.load_alerts() == old_entries
