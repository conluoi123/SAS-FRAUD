from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

import requests

from app.streamlit_console import alert_log
from app.streamlit_console.application_batch import (
    application_csv_template,
    claim_batch_run,
    execute_application_batch,
    invalid_batch_results,
    map_application_csv_row,
    parse_application_csv,
    payload_contains_null_strings,
    results_to_csv,
)
from app.streamlit_console.application_config import (
    AF_CIC_PROFILE_CAPACITY,
    APPLICATION_CHANNELS,
)
from app.streamlit_console.application_scenarios import (
    APPLICATION_SCENARIOS,
    calculate_30d_counts,
    expected_application_rules,
    normalize_address,
    scenario_history,
)
from app.streamlit_console.application_demo import (
    DEMO_SPECS,
    build_demo1_steps,
    build_demo2_steps,
    build_demo3_steps,
    run_demo_steps,
)
from app.streamlit_console.application_workspace import (
    MANUAL_PROFILE_KEYS,
    _build_quick_demo_dialog_entry,
    _display_outcome,
    _fired_rules_table_rows,
    _manual_result_identity,
    _rule_matches_target,
    apply_fresh_test_dataset,
    apply_new_application_same_customer,
)
from app.streamlit_console.payloads import (
    build_application_fraud_payload,
    validate_application_fraud_payload,
)
from app.streamlit_console.sas_client import SasRuntimeResponse
from app.streamlit_console.sas_response import extract_application_fired_rules


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
    assert message["solution"] == {
        "originationType": "AP",
        "activityType": "SB",
        "authenticationType": "NA",
        "channelType": "WB",
        "customerType": "IN",
    }
    assert message["application"]["identifier"].startswith("APP-20260904-")
    assert message["customer"]["identifier"] == "CUST-41127322"
    assert message["applicant"]["identifier"] == "APL-BANKA-0001"
    assert message["identification"]["number"] == "079099009999"
    assert message["applicant"]["monthlyRegularIncome"] == 25_000_000.0
    assert message["applicant"]["employment"] == [
        {"employerName": "Demo Company", "status": "EMPLOYED"}
    ]
    assert "employment" not in message
    assert message["device"]["ipAddress"] == "203.0.113.42"
    assert "cic" not in message
    assert "CIC" not in message
    assert "disbAcctCustCnt30d" not in message["appRisk"]
    assert "incomeMismatchInd" not in message["appRisk"]
    assert message["appRisk"]["employerUnverifiedInd"] == 0
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


def test_validator_rejects_negative_amount_and_channel_mismatch() -> None:
    payload = build_application_fraud_payload(
        {**BASE_VALUES, "application_amount": -1.0}
    )

    payload["message"]["solution"]["channelType"] = "MA"
    errors = validate_application_fraud_payload(payload)

    assert any("application.amount must not be negative" in error for error in errors)
    assert any("configured mapping" in error for error in errors)


def test_all_application_channels_map_in_sync() -> None:
    expected = {
        "MOBILE_APP": "MA",
        "WEB": "WB",
        "BRANCH": "BR",
        "SALES_AGENT": "SA",
        "PARTNER": "PT",
        "CALL_CENTER": "CC",
    }
    assert {
        name: config["solution_channel_type"]
        for name, config in APPLICATION_CHANNELS.items()
    } == expected
    for channel, channel_type in expected.items():
        message = build_application_fraud_payload(
            {**BASE_VALUES, "application_channel": channel}
        )["message"]
        assert message["application"]["channel"] == channel
        assert message["solution"]["channelType"] == channel_type


def test_invalid_application_channel_is_rejected() -> None:
    try:
        build_application_fraud_payload(
            {**BASE_VALUES, "application_channel": "UNSUPPORTED"}
        )
    except ValueError as error:
        assert "application.channel must be one of" in str(error)
    else:
        raise AssertionError("invalid channel was accepted")


def test_cic_profile_capacity_stays_at_ten_and_is_not_an_input() -> None:
    assert AF_CIC_PROFILE_CAPACITY == 10
    header = application_csv_template().decode("utf-8-sig").splitlines()[0]
    for excluded in (
        "cicApplicationIds",
        "cicInquiryDtTms",
        "solutionChannelType",
        "transactionIdentifier",
        "messageDtTmUtc",
        "firedFlg",
        "alertFlg",
    ):
        assert excluded not in header


def _two_row_csv() -> bytes:
    source = application_csv_template().decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(source)))
    second = dict(rows[0])
    second["applicationIdentifier"] = "APP-000002"
    second["customerIdentifier"] = "CUST-000002"
    second["applicationChannel"] = "CALL_CENTER"
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=rows[0].keys(), lineterminator="\n")
    writer.writeheader()
    writer.writerows([rows[0], second])
    return output.getvalue().encode("utf-8-sig")


def test_csv_parser_preserves_leading_zeros_and_never_emits_nan() -> None:
    validation = parse_application_csv(application_csv_template())
    assert validation.errors == []
    assert len(validation.valid_rows) == 1
    payload = map_application_csv_row(validation.valid_rows[0])
    assert payload["message"]["identification"]["number"] == "079099009999"
    assert payload["message"]["phone"]["full"] == "0901234567"
    assert payload["message"]["appRisk"]["disbAcctNumber"] == "09704000012345"
    assert payload_contains_null_strings(payload) is False


def test_csv_parser_rejects_invalid_channel_and_duplicate_application_id() -> None:
    source = _two_row_csv().decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(source)))
    rows[1]["applicationIdentifier"] = rows[0]["applicationIdentifier"]
    rows[1]["applicationChannel"] = "MOBILE"
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=rows[0].keys(), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

    validation = parse_application_csv(output.getvalue().encode("utf-8"))

    reasons = [item["reason"] for item in validation.errors]
    assert any("Duplicate application ID" in reason for reason in reasons)
    assert any("outside APPLICATION_CHANNELS" in reason for reason in reasons)
    assert len(validation.valid_rows) == 1


def test_csv_parser_reports_blank_rows_and_duplicate_headers() -> None:
    with_blank_row = application_csv_template().decode("utf-8-sig") + "\n"
    validation = parse_application_csv(with_blank_row.encode("utf-8"))
    assert any(item["reason"] == "Blank row" for item in validation.errors)
    assert invalid_batch_results(validation)[0]["requestStatus"] == (
        "Payload không hợp lệ"
    )

    duplicate_header = b"applicationIdentifier,applicationIdentifier\nAPP-1,APP-2\n"
    duplicate_validation = parse_application_csv(duplicate_header)
    assert any(
        item["reason"] == "Duplicate CSV header"
        for item in duplicate_validation.errors
    )


def test_batch_is_sequential_and_distinguishes_rule_from_alert() -> None:
    validation = parse_application_csv(_two_row_csv())
    sent_ids: list[str] = []
    sleeps: list[float] = []

    def sender(**kwargs):
        application_id = kwargs["payload"]["message"]["application"]["identifier"]
        sent_ids.append(application_id)
        has_alert = application_id == "APP-000002"
        parsed = {
            "message": {
                "sas": {
                    "system": {"returnType": 0},
                    "decision": {"outcomeName": "Review" if has_alert else "Continue"},
                    "rulefired": [
                        {
                            "ruleIdentifier": "AF_TEST",
                            "firedFlg": has_alert,
                            "alertFlg": has_alert,
                        }
                    ],
                    "alerted": ([{"outcomeEntity": application_id}] if has_alert else []),
                }
            }
        }
        return SasRuntimeResponse(200, 12, {}, "{}", parsed, None)

    results = execute_application_batch(
        validation.valid_rows,
        endpoint="https://runtime.example/detection/decision/execute",
        timeout_seconds=10,
        verify_tls=True,
        ca_bundle=None,
        delay_seconds=0.5,
        sender=sender,
        sleep=sleeps.append,
    )

    assert sent_ids == ["APP-000001", "APP-000002"]
    assert sleeps == [0.5]
    assert results[0]["requestStatus"] == "Request thành công"
    assert results[0]["firedFlg"] is False
    assert results[0]["alertFlg"] is False
    assert results[1]["firedFlg"] is True
    assert results[1]["alertFlg"] is True


def test_batch_does_not_retry_http_response() -> None:
    validation = parse_application_csv(application_csv_template())
    calls = 0

    def sender(**kwargs):
        nonlocal calls
        calls += 1
        return SasRuntimeResponse(500, 8, {}, "failure", None, "invalid response")

    results = execute_application_batch(
        validation.valid_rows,
        endpoint="https://runtime.example/detection/decision/execute",
        timeout_seconds=10,
        verify_tls=True,
        ca_bundle=None,
        delay_seconds=0,
        sender=sender,
    )

    assert calls == 1
    assert results[0]["errorType"] == "HTTP 5xx"


def test_batch_classifies_timeout_and_stops_when_requested() -> None:
    validation = parse_application_csv(_two_row_csv())
    calls = 0

    def sender(**kwargs):
        nonlocal calls
        calls += 1
        raise requests.Timeout("runtime timed out")

    results = execute_application_batch(
        validation.valid_rows,
        endpoint="https://runtime.example/detection/decision/execute",
        timeout_seconds=10,
        verify_tls=True,
        ca_bundle=None,
        delay_seconds=0,
        stop_on_error=True,
        sender=sender,
    )

    assert calls == 1
    assert len(results) == 1
    assert results[0]["errorType"] == "Timeout"


def test_batch_run_guard_blocks_rerun_and_double_click() -> None:
    state: dict[str, object] = {}
    assert claim_batch_run(state, "file-a") is True
    assert claim_batch_run(state, "file-a") is False
    state["af_batch_running"] = False
    state["af_batch_completed_fingerprint"] = "file-a"
    assert claim_batch_run(state, "file-a") is False


def test_result_csv_keeps_sensitive_identifiers_as_strings() -> None:
    validation = parse_application_csv(application_csv_template())
    payload = map_application_csv_row(validation.valid_rows[0])
    exported = results_to_csv(
        [
            {
                "rowNumber": 2,
                "applicationIdentifier": "APP-000001",
                "_request": payload,
                "_rawResponse": "{}",
            }
        ]
    ).decode("utf-8-sig")

    assert "079099009999" in exported
    assert "0901234567" in exported
    assert "09704000012345" in exported


def _parsed_with_rules(rules: list[dict]) -> dict:
    return {"message": {"sas": {"rulefired": rules}}}


def test_fired_rule_prefers_human_readable_name_over_uuid() -> None:
    parsed = _parsed_with_rules(
        [
            {
                "ruleIdentifier": "0cfc3922-fe7c-4224-9a2f-c3140ccab1b0",
                "ruleName": "AF_DR_Disbursement_Account_Anomaly",
                "firedFlg": True,
                "alertFlg": True,
            }
        ]
    )
    fired = extract_application_fired_rules(parsed)
    assert len(fired) == 1
    assert fired[0].display_name == "AF_DR_Disbursement_Account_Anomaly"
    assert fired[0].name_basis == "ruleName"
    assert fired[0].rule_identifier == "0cfc3922-fe7c-4224-9a2f-c3140ccab1b0"


def test_fired_rule_falls_back_to_unknown_when_only_uuid_is_present() -> None:
    # This UUID is deliberately NOT one of the verified identifiers in
    # sas_response._VERIFIED_RULE_NAMES, so the fallback path must be exercised
    # instead of inventing a business name for it.
    unmapped_identifier = "11111111-2222-3333-4444-555555555555"
    parsed = _parsed_with_rules(
        [{"ruleIdentifier": unmapped_identifier, "firedFlg": True}]
    )
    fired = extract_application_fired_rules(parsed)
    assert fired[0].name_basis == "identifier"
    assert unmapped_identifier in fired[0].display_name


def test_verified_identifier_resolves_to_business_rule_name_from_live_sas() -> None:
    # These two mappings were captured from real, live SAS responses in this
    # session (Quick Demo 1 and Demo 2) — see the comment above
    # sas_response._VERIFIED_RULE_NAMES for provenance. The reason text is
    # still preserved separately so nothing SAS said is lost.
    parsed = _parsed_with_rules(
        [
            {
                "ruleIdentifier": "cc5fb2bb-4dba-4828-9ae1-0f30000db36a",
                "referenceIdentifier": "50082.2",
                "alertReason": "Shared non-matching disbursement account",
                "firedFlg": True,
                "alertFlg": True,
            }
        ]
    )
    fired = extract_application_fired_rules(parsed)
    assert fired[0].display_name == "AF_DR_Disbursement_Account_Anomaly"
    assert fired[0].name_basis == "verified_mapping"
    assert fired[0].reason == "Shared non-matching disbursement account"
    assert fired[0].rule_reference == "50082.2"


def test_not_fired_rules_are_excluded_by_default() -> None:
    parsed = _parsed_with_rules(
        [
            {"ruleIdentifier": "A", "ruleName": "Rule A", "firedFlg": False},
            {"ruleIdentifier": "B", "ruleName": "Rule B", "firedFlg": True},
        ]
    )
    fired = extract_application_fired_rules(parsed)
    assert len(fired) == 1
    assert fired[0].display_name == "Rule B"


def test_multiple_fired_rules_are_all_returned() -> None:
    parsed = _parsed_with_rules(
        [
            {
                "ruleIdentifier": "A",
                "ruleName": "AF_DR_Disbursement_Account_Anomaly",
                "firedFlg": True,
                "alertFlg": True,
            },
            {
                "ruleIdentifier": "B",
                "ruleName": "AF_DR_Shared_Reference_Network",
                "firedFlg": True,
                "alertFlg": True,
            },
        ]
    )
    fired = extract_application_fired_rules(parsed)
    names = {rule.display_name for rule in fired}
    assert names == {"AF_DR_Disbursement_Account_Anomaly", "AF_DR_Shared_Reference_Network"}


def test_raw_identifier_stays_available_in_display_table() -> None:
    parsed = _parsed_with_rules(
        [
            {
                "ruleIdentifier": "0cfc3922-fe7c-4224-9a2f-c3140ccab1b0",
                "ruleName": "AF_DR_Disbursement_Account_Anomaly",
                "firedFlg": True,
                "alertFlg": True,
            }
        ]
    )
    fired = extract_application_fired_rules(parsed)
    rows = _fired_rules_table_rows(fired)
    assert rows[0]["Rule identifier"] == "0cfc3922-fe7c-4224-9a2f-c3140ccab1b0"


def test_target_rule_is_matched_independently_of_display_name() -> None:
    parsed = _parsed_with_rules(
        [
            {
                "ruleIdentifier": "A",
                "ruleName": "AF_DR_Disbursement_Account_Anomaly",
                "firedFlg": True,
                "alertFlg": True,
            }
        ]
    )
    fired = extract_application_fired_rules(parsed)
    assert _rule_matches_target(fired[0], "AF_DR_Disbursement_Account_Anomaly") is True
    assert _rule_matches_target(fired[0], "AF_DR_Shared_Reference_Network") is False


def test_target_rule_matches_via_verified_mapping_like_the_live_runtime_does() -> None:
    # Mirrors the exact shape captured from the live SAS runtime for Demo 1's
    # trigger step: no ruleName/ruleReference field, only ruleIdentifier,
    # referenceIdentifier, and alertReason.
    parsed = _parsed_with_rules(
        [
            {
                "ruleIdentifier": "cc5fb2bb-4dba-4828-9ae1-0f30000db36a",
                "referenceIdentifier": "50082.2",
                "alertReason": "Shared non-matching disbursement account",
                "firedFlg": True,
                "alertFlg": True,
                "outcomeEntity": "APP-DEMO-D1B-B7C7B1AA",
                "outcomeEntityType": "app_fraud_app",
            }
        ]
    )
    fired = extract_application_fired_rules(parsed)
    assert _rule_matches_target(fired[0], "AF_DR_Disbursement_Account_Anomaly") is True


def _forbidden_profile_fields_absent(payload: dict) -> bool:
    app_risk = payload["message"]["appRisk"]
    forbidden = {
        "disbAcctCustCnt30d",
        "refPhoneCustCnt30d",
        "addressCustCnt30d",
        "clusterCustCnt30d",
    }
    return forbidden.isdisjoint(app_risk)


def test_demo1_shares_only_the_intended_disbursement_account() -> None:
    steps = build_demo1_steps()
    assert len(steps) == 2
    seed_payload = build_application_fraud_payload(steps[0].values)
    trigger_payload = build_application_fraud_payload(steps[1].values)

    assert validate_application_fraud_payload(seed_payload) == []
    assert validate_application_fraud_payload(trigger_payload) == []
    assert _forbidden_profile_fields_absent(seed_payload)
    assert _forbidden_profile_fields_absent(trigger_payload)

    seed_risk = seed_payload["message"]["appRisk"]
    trigger_risk = trigger_payload["message"]["appRisk"]
    assert seed_risk["disbAcctNumber"] == trigger_risk["disbAcctNumber"]
    assert seed_risk["disbAcctOwnerMatchInd"] == 1
    assert trigger_risk["disbAcctOwnerMatchInd"] == 0
    assert (
        seed_payload["message"]["application"]["identifier"]
        != trigger_payload["message"]["application"]["identifier"]
    )
    assert (
        seed_payload["message"]["customer"]["identifier"]
        != trigger_payload["message"]["customer"]["identifier"]
    )


def test_demo2_shares_reference_phone_and_partial_account_overlap() -> None:
    steps = build_demo2_steps()
    assert len(steps) == 3
    payloads = [build_application_fraud_payload(step.values) for step in steps]
    for payload in payloads:
        assert validate_application_fraud_payload(payload) == []
        assert _forbidden_profile_fields_absent(payload)

    phones = {p["message"]["appRisk"]["referencePhone"] for p in payloads}
    assert len(phones) == 1

    accounts = [p["message"]["appRisk"]["disbAcctNumber"] for p in payloads]
    assert accounts[0] == accounts[2]
    assert accounts[1] != accounts[0]

    customer_ids = {p["message"]["customer"]["identifier"] for p in payloads}
    assert len(customer_ids) == 3


def test_demo3_shares_address_employer_and_sales_agent() -> None:
    steps = build_demo3_steps()
    assert len(steps) == 4
    payloads = [build_application_fraud_payload(step.values) for step in steps]
    for payload in payloads:
        assert validate_application_fraud_payload(payload) == []
        assert _forbidden_profile_fields_absent(payload)

    addresses = {p["message"]["appRisk"]["normalizedAddress"] for p in payloads}
    agents = {p["message"]["appRisk"]["salesAgentIdentifier"] for p in payloads}
    employers = {
        p["message"]["applicant"]["employment"][0]["employerName"] for p in payloads
    }
    assert len(addresses) == 1
    assert len(agents) == 1
    assert len(employers) == 1

    customer_ids = {p["message"]["customer"]["identifier"] for p in payloads}
    assert len(customer_ids) == 4


def test_demo_steps_are_sent_sequentially_and_stop_on_failed_seed() -> None:
    steps = build_demo1_steps()
    calls: list[str] = []

    def sender(**kwargs):
        application_id = kwargs["payload"]["message"]["application"]["identifier"]
        calls.append(application_id)
        return SasRuntimeResponse(500, 10, {}, "boom", None, None)

    results = run_demo_steps(
        steps,
        endpoint="https://runtime.example/detection/decision/execute",
        timeout_seconds=10,
        verify_tls=True,
        ca_bundle=None,
        sender=sender,
    )

    assert len(calls) == 1
    assert len(results) == 1
    assert results[0]["response"].status_code == 500


def test_demo_steps_continue_while_http_is_successful() -> None:
    steps = build_demo1_steps()
    calls: list[str] = []

    def sender(**kwargs):
        calls.append(kwargs["payload"]["message"]["application"]["identifier"])
        return SasRuntimeResponse(200, 10, {}, "{}", {"message": {"sas": {}}}, None)

    results = run_demo_steps(
        steps,
        endpoint="https://runtime.example/detection/decision/execute",
        timeout_seconds=10,
        verify_tls=True,
        ca_bundle=None,
        sender=sender,
    )

    assert len(calls) == 2
    assert len(results) == 2


def test_demo4_target_rule_is_not_registered_as_a_quick_demo() -> None:
    # Income/employer inconsistency stays disabled until incomeMismatchInd has a
    # verified outbound message path — it must not appear as a runnable demo.
    assert set(DEMO_SPECS) == {"demo1", "demo2", "demo3"}


# --- UI/state separation between Quick Demo and the manual workflow ---------


def test_quick_demo_state_keys_are_disjoint_from_manual_state_keys() -> None:
    demo_keys = {"af_demo1_result", "af_demo2_result", "af_demo3_result", "af_demo_pending_dialog"}
    manual_keys = {
        "af_single_result",
        "af_single_last_transaction",
        "af_single_application_id",
        "af_single_transaction_id",
        "af_pending_result_dialog",
        *MANUAL_PROFILE_KEYS,
    }
    assert demo_keys.isdisjoint(manual_keys)


def test_manual_profile_keys_cover_every_profile_driving_field() -> None:
    assert set(MANUAL_PROFILE_KEYS) == {
        "af_single_applicant_id",
        "af_single_customer_id",
        "af_single_identification_number",
        "af_single_phone",
        "af_single_device_id",
        "af_single_disb_account",
        "af_single_reference_phone",
        "af_single_normalized_address",
        "af_single_sales_agent",
    }


def _fake_manual_state() -> dict[str, object]:
    return {
        "af_single_application_id": "APP-OLD",
        "af_single_transaction_id": "MSG-OLD",
        "af_single_applicant_id": "APL-OLD",
        "af_single_customer_id": "CUST-OLD",
        "af_single_identification_number": "079099009999",
        "af_single_phone": "0901234567",
        "af_single_device_id": "DEV-OLD",
        "af_single_disb_account": "09704000012345",
        "af_single_reference_phone": "0912345678",
        "af_single_normalized_address": "88 CONG HOA TP HCM",
        "af_single_sales_agent": "SALES-001",
        "af_single_last_transaction": "MSG-OLD",
        "af_single_result": {"payload": {"message": {}}, "response": "stale"},
        "af_demo1_result": ["should not be touched"],
        "af_demo2_result": ["should not be touched"],
        "af_demo3_result": ["should not be touched"],
        "af_demo_pending_dialog": {"should": "not be touched"},
    }


def test_new_application_same_customer_only_changes_application_and_transaction() -> None:
    state = _fake_manual_state()
    apply_new_application_same_customer(state)

    assert state["af_single_application_id"] != "APP-OLD"
    assert state["af_single_transaction_id"] != "MSG-OLD"
    assert state["af_single_last_transaction"] is None
    # Every profile-driving key is untouched — same identity, new application.
    for key in MANUAL_PROFILE_KEYS:
        assert state[key] == _fake_manual_state()[key]
    # Quick Demo state must never be written by the manual reset actions.
    assert state["af_demo1_result"] == ["should not be touched"]
    assert state["af_demo2_result"] == ["should not be touched"]
    assert state["af_demo3_result"] == ["should not be touched"]
    assert state["af_demo_pending_dialog"] == {"should": "not be touched"}


def test_fresh_test_dataset_regenerates_every_profile_driving_key() -> None:
    original = _fake_manual_state()
    state = _fake_manual_state()
    apply_fresh_test_dataset(state)

    assert state["af_single_application_id"] != original["af_single_application_id"]
    assert state["af_single_transaction_id"] != original["af_single_transaction_id"]
    for key in MANUAL_PROFILE_KEYS:
        assert state[key] != original[key], f"{key} was not regenerated"

    # New identification/phone/reference phone/disbursement account stay digits-only.
    assert state["af_single_identification_number"].isdigit()
    assert len(state["af_single_identification_number"]) == 12
    assert state["af_single_phone"].isdigit()
    assert state["af_single_reference_phone"].isdigit()
    assert len(state["af_single_reference_phone"]) == 10
    assert state["af_single_disb_account"].isdigit()

    # Quick Demo state must never be written by the manual reset actions.
    assert state["af_demo1_result"] == ["should not be touched"]
    assert state["af_demo2_result"] == ["should not be touched"]
    assert state["af_demo3_result"] == ["should not be touched"]
    assert state["af_demo_pending_dialog"] == {"should": "not be touched"}


def test_fresh_test_dataset_clears_stale_manual_result() -> None:
    state = _fake_manual_state()
    apply_fresh_test_dataset(state)

    assert state["af_single_result"] is None
    assert state["af_single_last_transaction"] is None


# --- manual result metadata comes from the sent payload, not live form state ---


def test_manual_result_identity_reads_from_sent_payload_only() -> None:
    result = {
        "payload": {
            "message": {
                "application": {"identifier": "APP-SENT-001"},
                "customer": {"identifier": "CUST-SENT-001"},
                "sas": {"system": {"transactionIdentifier": "MSG-SENT-001"}},
            }
        },
        "response": SasRuntimeResponse(200, 10, {}, "{}", {"message": {}}, None),
        "sent_at": "2026-09-09T01:00:00Z",
    }
    identity = _manual_result_identity(result)

    assert identity == {
        "application_identifier": "APP-SENT-001",
        "customer_identifier": "CUST-SENT-001",
        "transaction_identifier": "MSG-SENT-001",
        "sent_at": "2026-09-09T01:00:00Z",
    }


def test_display_outcome_never_fakes_review_or_decline() -> None:
    assert _display_outcome(None) == "No explicit outcome"
    assert _display_outcome("Unknown") == "No explicit outcome"
    assert _display_outcome("") == "No explicit outcome"
    assert _display_outcome("Review") == "Review"
    assert _display_outcome("Decline") == "Decline"


# --- Quick Demo popup only opens for the final (trigger) step ---------------


def test_quick_demo_dialog_only_built_when_final_step_creates_an_alert() -> None:
    spec = DEMO_SPECS["demo1"]
    payload = {
        "message": {
            "application": {"identifier": "APP-DEMO-TRIGGER"},
            "customer": {"identifier": "CUST-DEMO-TRIGGER"},
        }
    }

    no_alert_response = SasRuntimeResponse(
        200, 10, {}, "{}", {"message": {"sas": {"rulefired": []}}}, None
    )
    assert _build_quick_demo_dialog_entry(spec, payload, no_alert_response) is None

    alert_response = SasRuntimeResponse(
        200,
        10,
        {},
        "{}",
        {
            "message": {
                "sas": {
                    "rulefired": [
                        {
                            "ruleIdentifier": "cc5fb2bb-4dba-4828-9ae1-0f30000db36a",
                            "referenceIdentifier": "50082.2",
                            "alertReason": "Shared non-matching disbursement account",
                            "firedFlg": True,
                            "alertFlg": True,
                        }
                    ]
                }
            }
        },
        None,
    )
    entry = _build_quick_demo_dialog_entry(spec, payload, alert_response)
    assert entry is not None
    assert entry["target_rule"] == "AF_DR_Disbursement_Account_Anomaly"
    assert entry["actual_rule_name"] == "AF_DR_Disbursement_Account_Anomaly"
    assert entry["application_identifier"] == "APP-DEMO-TRIGGER"
    assert entry["customer_identifier"] == "CUST-DEMO-TRIGGER"


# --- stale hardcoded package version must not be the primary runtime display ---


def test_no_hardcoded_package_version_in_application_workspace_source() -> None:
    import inspect

    from app.streamlit_console import application_workspace

    source = inspect.getsource(application_workspace)
    assert "50026" not in source


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
