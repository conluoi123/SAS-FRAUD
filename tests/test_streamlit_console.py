import json

from app.streamlit_console.payloads import build_payment_fraud_payload
from app.streamlit_console.sas_response import (
    extract_return_fields,
    parse_sas_response,
    summarize_sas_response,
)
from app.streamlit_console.scenarios import (
    SCENARIOS,
    scenario_by_key,
)


def test_parse_sas_text_response_and_summarize_alert() -> None:
    inner = (
        '{message:{sas:{decision:{outcome:40,outcomeName:"Decline",'
        'referenceIdentifier:"50007.1"},alerted:[{outcomeEntity:"CARD-1",'
        'outcomeEntityType:"sfd_creditcard"}],rulefired:[{alertFlg:true,'
        'firedFlg:true,elapsed:10,ruleIdentifier:"RULE-1"},{alertFlg:false,'
        'firedFlg:false,elapsed:2,ruleIdentifier:"RULE-2"}],system:{'
        'messageIdentifier:"MSG-1",transactionIdentifier:"TXN-1"},timings:{'
        "profileFetch:150,rules:54,total:1329}}},profiles:{SAS_CreditCard:{"
        "currentMessageDtTm:2026-06-05T02:20:00.000000000Z,lastMessageDtTm:null}}}"
    )
    parsed = parse_sas_response(json.dumps(inner))
    summary = summarize_sas_response(parsed)

    assert parsed["profiles"]["SAS_CreditCard"]["currentMessageDtTm"] == (
        "2026-06-05T02:20:00.000000000Z"
    )
    assert summary.outcome == 40
    assert summary.outcome_name == "Decline"
    assert summary.alert_created is True
    assert summary.evaluated_rule_count == 2
    assert len(summary.fired_rules) == 1
    assert summary.timings["total"] == 1329


def test_parse_standard_json_response() -> None:
    assert parse_sas_response('{"status":"ok"}') == {"status": "ok"}


def test_summary_accepts_alerted_and_rule_alert_flags() -> None:
    parsed = {
        "message": {
            "sas": {
                "alerted": {
                    "outcomeEntity": "APP-1",
                    "outcomeEntityType": "sfd_application",
                },
                "rulefired": [{"alertFlg": True, "ruleIdentifier": "AF_DR_TEST"}],
            }
        }
    }

    summary = summarize_sas_response(parsed)

    assert summary.alert_created is True
    assert summary.alerted_entities[0]["outcomeEntity"] == "APP-1"
    assert summary.fired_rules[0]["ruleIdentifier"] == "AF_DR_TEST"


def test_extract_return_fields_from_sas_system() -> None:
    parsed = {
        "message": {
            "sas": {
                "system": {"returnType": 0, "returnDesc": "OK", "returnDetails": "Done"}
            }
        }
    }

    assert extract_return_fields(parsed) == {
        "returnType": 0,
        "returnDesc": "OK",
        "returnDetails": "Done",
    }


def test_build_payment_fraud_payload_keeps_profile_and_transaction_keys() -> None:
    values = {
        "origination_type": "CC",
        "activity_type": "CT",
        "authentication_type": "PIN",
        "channel_type": "ATM",
        "customer_type": "INDIVIDUAL",
        "message_classification": "Southeast",
        "message_datetime": "2026-06-05T02:20:00Z",
        "customer_identifier": "CUST-1",
        "customer_surname": "Carlyle",
        "customer_country": "US",
        "credit_card_number": "4111111111111114",
        "credit_card_limit": 5000,
        "cardholder_country": "US",
        "debit_account_number": "DA-CUST-1",
        "debit_card_number": "DC-CUST-1",
        "transaction_identifier": "TXN-1",
        "transaction_amount": 700,
        "card_amount": 500,
        "usd_amount": 500,
        "currency_code": "USD",
        "card_present_ind": "1",
        "customer_present_ind": "1",
        "device_identifier": "DEV-1",
        "device_fingerprint": "FP-1",
        "device_fingerprint_type": "SAS",
        "device_ip_address": "203.0.113.42",
        "auth_decision": "DENY",
        "auth_level": "LOW",
        "auth_result": "FAILURE",
        "auth_type": "3DS_V2",
        "ecommerce_authentication": "FAILED",
        "merchant_name": "ATM TOKYO CENTRAL",
        "merchant_category_code": "6011",
        "merchant_country": "JP",
    }

    payload = build_payment_fraud_payload(values)
    message = payload["message"]

    assert message["request"]["schemaName"] == "Payment Fraud"
    assert message["request"]["messageClassificationName"] == "Southeast"
    assert message["creditcard"]["number"] == "4111111111111114"
    assert message["debitcard"]["number"] == "DC-CUST-1"
    assert message["device"]["identifier"] == "DEV-1"
    assert message["device"]["fingerprint"] == ["FP-1"]
    assert "auth" not in message
    assert message["authentication"]["decision"] == "DENY"
    assert message["cardfinancial"]["ecommerceAuthentication"] == "FAILED"
    assert message["sas"]["system"]["transactionIdentifier"] == "TXN-1"
    assert "subscriptionIdentifier" not in message["merchant"]
    assert "digital" not in message


BASE_VALUES = {
    "origination_type": "DC",
    "activity_type": "CA",
    "authentication_type": "NONE",
    "channel_type": "WEB",
    "customer_type": "INDIVIDUAL",
    "message_classification": "GLOBAL",
    "message_datetime": "2026-06-05T02:20:00Z",
    "customer_identifier": "CUST-1",
    "customer_surname": "Carlyle",
    "customer_country": "US",
    "credit_card_number": "4111111111111114",
    "credit_card_limit": 5000,
    "cardholder_country": "US",
    "debit_account_number": "DA-CUST-1",
    "debit_card_number": "DC-CUST-1",
    "transaction_identifier": "TXN-1",
    "transaction_amount": 700,
    "card_amount": 750,
    "usd_amount": 500,
    "currency_code": "USD",
    "card_present_ind": "1",
    "customer_present_ind": "1",
    "device_identifier": "DEV-NEW-9001",
    "device_fingerprint": "FP-1",
    "device_fingerprint_type": "SAS",
    "device_ip_address": "203.0.113.42",
    "known_device_1": "DEV-KNOWN-001",
    "known_device_2": "DEV-KNOWN-002",
    "known_device_3": "DEV-KNOWN-003",
    "auth_decision": "DENY",
    "auth_level": "LOW",
    "auth_result": "FAILURE",
    "auth_type": "3DS_V2",
    "ecommerce_authentication": "FAILED",
    "merchant_name": "ECOM DIGITAL STORE",
    "merchant_category_code": "5732",
    "merchant_country": "US",
    "subscription_identifier": "",
    "structuring_reference_threshold": 500.0,
    "ip_country_code": "",
    "chargeback_reference_number": "",
    "chargeback_identifier": "",
    "chargeback_amount": 0.0,
    "chargeback_payment_method": "",
    "chargeback_purchase_dttm": "",
    "chargeback_misc_data": "",
}


def test_build_payment_fraud_payload_includes_optional_fields_when_present() -> None:
    values = {
        **BASE_VALUES,
        "subscription_identifier": "SUB-001",
        "ip_country_code": "VN",
    }

    payload = build_payment_fraud_payload(values)
    message = payload["message"]

    assert message["merchant"]["subscriptionIdentifier"] == "SUB-001"
    assert message["digital"]["ipCountryCode"] == "VN"


def test_build_payment_fraud_payload_includes_chargeback_when_reference_present() -> (
    None
):
    values = {
        **BASE_VALUES,
        "activity_type": "CB",
        "chargeback_reference_number": "REF-0001",
        "chargeback_identifier": "PMT-0001",
        "chargeback_amount": 750.0,
        "chargeback_payment_method": "1",
        "chargeback_purchase_dttm": "2026-05-01T10:00:00Z",
    }

    payload = build_payment_fraud_payload(values)
    message = payload["message"]

    assert message["chargeback"]["referenceNumber"] == "REF-0001"
    assert message["chargeback"]["identifier"] == "PMT-0001"
    assert message["chargeback"]["amount"] == 750.0
    assert message["chargeback"]["paymentMethod"] == "1"


def test_build_payment_fraud_payload_omits_chargeback_when_reference_blank() -> None:
    payload = build_payment_fraud_payload(BASE_VALUES)
    assert "chargeback" not in payload["message"]


def test_chargeback_abuse_checks_fail_on_wrong_activity_type() -> None:
    scenario = scenario_by_key("chargeback_abuse")
    values = {
        **BASE_VALUES,
        "activity_type": "CA",
        "chargeback_reference_number": "REF-0001",
    }
    checks = scenario.checks(values)
    routing_check = next(
        check for check in checks if check["Condition"].startswith("Chargeback routing")
    )
    assert routing_check["Pass"] is False


def test_chargeback_abuse_checks_pass_on_expected_routing() -> None:
    scenario = scenario_by_key("chargeback_abuse")
    values = {
        **BASE_VALUES,
        "activity_type": "CB",
        "chargeback_reference_number": "REF-0001",
    }
    checks = scenario.checks(values)
    assert all(check["Pass"] for check in checks)


def test_scenario_keys_are_unique() -> None:
    keys = [scenario.key for scenario in SCENARIOS]
    assert len(keys) == len(set(keys))


def test_cnp_new_device_checks_pass_on_trigger_preset() -> None:
    scenario = scenario_by_key("cnp_new_device")
    checks = scenario.checks(BASE_VALUES)
    assert all(check["Pass"] for check in checks)


def test_cnp_risky_mcc_checks_fail_on_non_risky_mcc() -> None:
    scenario = scenario_by_key("cnp_risky_mcc")
    values = {**BASE_VALUES, "card_amount": 400, "merchant_category_code": "5411"}
    checks = scenario.checks(values)
    mcc_check = next(check for check in checks if check["Condition"] == "Risky MCC")
    assert mcc_check["Pass"] is False


def test_cnp_risky_mcc_checks_pass_on_risky_mcc() -> None:
    scenario = scenario_by_key("cnp_risky_mcc")
    values = {**BASE_VALUES, "card_amount": 400, "merchant_category_code": "7995"}
    checks = scenario.checks(values)
    assert all(check["Pass"] for check in checks)


def test_subscription_testing_checks_require_failed_auth() -> None:
    scenario = scenario_by_key("cnp_subscription_testing")
    values = {
        **BASE_VALUES,
        "subscription_identifier": "SUB-001",
        "ecommerce_authentication": "SUCCESS",
    }
    checks = scenario.checks(values)
    auth_check = next(
        check for check in checks if check["Condition"].startswith("Failed/attempted")
    )
    assert auth_check["Pass"] is False


def test_structuring_checks_pass_when_amount_near_threshold() -> None:
    scenario = scenario_by_key("structuring")
    values = {
        **BASE_VALUES,
        "card_amount": 480,
        "structuring_reference_threshold": 500.0,
    }
    checks = scenario.checks(values)
    assert all(check["Pass"] for check in checks)


def test_structuring_checks_fail_when_amount_far_from_threshold() -> None:
    scenario = scenario_by_key("structuring")
    values = {
        **BASE_VALUES,
        "card_amount": 100,
        "structuring_reference_threshold": 500.0,
    }
    checks = scenario.checks(values)
    near_threshold_check = next(
        check for check in checks if check["Condition"].startswith("Amount near")
    )
    assert near_threshold_check["Pass"] is False
