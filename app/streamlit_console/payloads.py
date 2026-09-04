"""Payload builders for supported SAS message types."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


APPLICATION_FRAUD_SCHEMA = "Application Fraud"
APPLICATION_FRAUD_CLASSIFICATION = "GLOBAL"
APPLICATION_RISK_STRING_FIELDS = (
    "bankId",
    "salesAgentIdentifier",
    "disbAcctNumber",
    "referencePhone",
    "normalizedAddress",
)
APPLICATION_RISK_INTEGER_FIELDS = (
    "disbAcctOwnerMatchInd",
    "disbAcctCustCnt30d",
    "refPhoneCustCnt30d",
    "employerUnverifiedInd",
    "incomeMismatchInd",
    "addressCustCnt30d",
    "clusterCustCnt30d",
    "salesAgentAppCnt30d",
    "salesAgentLocRiskInd",
    "identityMismatchInd",
)


def _utc_iso8601(value: Any) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        source = value.strip()
        if source.endswith("Z"):
            source = f"{source[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(source)
        except ValueError as error:
            raise ValueError("message_datetime must be ISO-8601") from error
    else:
        raise ValueError("message_datetime is required")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (
        parsed.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _new_application_identifier(message_datetime: str) -> str:
    date_token = message_datetime[:10].replace("-", "")
    return f"APP-{date_token}-{uuid.uuid4().hex[:8].upper()}"


def _new_transaction_identifier() -> str:
    return f"MSG-{uuid.uuid4().hex[:16].upper()}"


def _object(**values: Any) -> dict[str, Any]:
    """Drop empty optional text while preserving numeric zero and false values."""

    return {
        key: value
        for key, value in values.items()
        if value is not None and (not isinstance(value, str) or value.strip())
    }


def build_application_fraud_payload(values: dict[str, Any]) -> dict[str, Any]:
    """Build the dedicated Application Fraud message contract."""

    message_datetime = _utc_iso8601(values.get("message_datetime"))
    application_identifier = str(
        values.get("application_identifier")
        or _new_application_identifier(message_datetime)
    ).strip()
    transaction_identifier = str(
        values.get("transaction_identifier") or _new_transaction_identifier()
    ).strip()
    app_risk = dict(values.get("app_risk") or {})

    message = {
        "request": {
            "command": "Execute",
            "decisioningInd": 1,
            "schemaName": APPLICATION_FRAUD_SCHEMA,
            "messageClassificationName": APPLICATION_FRAUD_CLASSIFICATION,
            "restResponseFlg": 1,
            "messageDtTm": message_datetime,
        },
        "sas": {
            "system": {
                "transactionIdentifier": transaction_identifier,
                "messageDtTmUtc": message_datetime,
            }
        },
        "application": _object(
            identifier=application_identifier,
            type=values.get("application_type"),
            amount=values.get("application_amount"),
            currencyCode=values.get("currency_code"),
            channel=values.get("application_channel"),
            purpose=values.get("application_purpose"),
            status=values.get("application_status"),
            stage=values.get("application_stage"),
        ),
        "applicant": _object(
            identifier=values.get("applicant_identifier"),
            name=values.get("applicant_name"),
            monthlyRegularIncome=values.get("monthly_regular_income"),
            outstandingDebt=values.get("outstanding_debt"),
        ),
        "customer": _object(
            identifier=values.get("customer_identifier"),
            surname=values.get("customer_name"),
            type=values.get("customer_type"),
            addressCountryCode=values.get("address_country_code"),
        ),
        "identification": _object(number=values.get("identification_number")),
        "emailaddress": _object(fullEmail=values.get("email")),
        "phone": _object(full=values.get("phone")),
        "employment": _object(
            employerName=values.get("employer_name"),
            status=values.get("employment_status"),
        ),
        "location": _object(monthsAtLocation=values.get("months_at_location")),
        "device": _object(
            identifier=values.get("device_identifier"),
            ipAddress=values.get("device_ip_address"),
        ),
        "cic": {
            "inquiryCount7Days": values.get("cic_inquiry_count_7_days"),
            "inquiryCount30Days": values.get("cic_inquiry_count_30_days"),
        },
        # Do not clean this object: SAS Profile must receive explicit zero values.
        "appRisk": app_risk,
    }
    return {"message": message}


def _value_at(root: dict[str, Any], *path: str) -> Any:
    current: Any = root
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_application_fraud_payload(payload: dict[str, Any]) -> list[str]:
    """Validate required Application Fraud fields before the SAS POST."""

    if not isinstance(payload, dict) or not isinstance(payload.get("message"), dict):
        return ["The root object must contain a message object."]

    errors: list[str] = []
    message = payload["message"]
    request = message.get("request", {})
    system = _value_at(message, "sas", "system") or {}
    if message.get("solution") is not None or "solution" in message:
        errors.append("Application Fraud payload must not contain message.solution.")
    if request.get("schemaName") != APPLICATION_FRAUD_SCHEMA:
        errors.append('request.schemaName must be "Application Fraud".')
    if request.get("messageClassificationName") != APPLICATION_FRAUD_CLASSIFICATION:
        errors.append('request.messageClassificationName must be "GLOBAL".')

    required_text = {
        "customer.identifier": _value_at(message, "customer", "identifier"),
        "applicant.identifier": _value_at(message, "applicant", "identifier"),
        "identification.number": _value_at(message, "identification", "number"),
        "application.identifier": _value_at(message, "application", "identifier"),
        "application.type": _value_at(message, "application", "type"),
        "application.currencyCode": _value_at(message, "application", "currencyCode"),
        "application.channel": _value_at(message, "application", "channel"),
        "device.identifier": _value_at(message, "device", "identifier"),
        "device.ipAddress": _value_at(message, "device", "ipAddress"),
        "sas.system.transactionIdentifier": system.get("transactionIdentifier"),
        "request.messageDtTm": request.get("messageDtTm"),
        "appRisk.bankId": _value_at(message, "appRisk", "bankId"),
        "appRisk.salesAgentIdentifier": _value_at(
            message, "appRisk", "salesAgentIdentifier"
        ),
    }
    for path, value in required_text.items():
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{path} is required.")

    application_identifier = required_text["application.identifier"]
    transaction_identifier = required_text["sas.system.transactionIdentifier"]
    if application_identifier and application_identifier == transaction_identifier:
        errors.append("Application ID and transaction ID must be different.")

    for path, value in {
        "application.amount": _value_at(message, "application", "amount"),
        "applicant.monthlyRegularIncome": _value_at(
            message, "applicant", "monthlyRegularIncome"
        ),
        "applicant.outstandingDebt": _value_at(message, "applicant", "outstandingDebt"),
        "cic.inquiryCount7Days": _value_at(message, "cic", "inquiryCount7Days"),
        "cic.inquiryCount30Days": _value_at(message, "cic", "inquiryCount30Days"),
    }.items():
        if not _is_number(value):
            errors.append(f"{path} must be numeric.")
        elif value < 0:
            errors.append(f"{path} must not be negative.")

    for path in ("request.messageDtTm", "sas.system.messageDtTmUtc"):
        value = (
            request.get("messageDtTm")
            if path.startswith("request")
            else system.get("messageDtTmUtc")
        )
        try:
            _utc_iso8601(value)
        except ValueError:
            errors.append(f"{path} must be a valid timestamp.")

    app_risk = message.get("appRisk")
    if not isinstance(app_risk, dict):
        errors.append("appRisk must be an object.")
        return errors
    for field_name in APPLICATION_RISK_STRING_FIELDS:
        value = app_risk.get(field_name)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"appRisk.{field_name} is required.")
    for field_name in APPLICATION_RISK_INTEGER_FIELDS:
        value = app_risk.get(field_name)
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"appRisk.{field_name} must be an integer.")
    risk_rate = app_risk.get("salesAgentRiskRate30d")
    if not _is_number(risk_rate):
        errors.append("appRisk.salesAgentRiskRate30d must be numeric.")
    return errors


def build_payment_fraud_payload(values: dict[str, Any]) -> dict[str, Any]:
    """Build the Payment Fraud envelope used by the current SAS deployment."""

    transaction_identifier = values["transaction_identifier"]
    message_datetime = values["message_datetime"]
    card_amount = float(values["card_amount"])
    transaction_amount = float(values["transaction_amount"])

    message: dict[str, Any] = {
        "solution": {
            "originationType": values["origination_type"],
            "activityType": values["activity_type"],
            "authenticationType": values["authentication_type"],
            "channelType": values["channel_type"],
            "customerType": values["customer_type"],
        },
        "request": {
            "command": "Execute",
            "decisioningInd": 1,
            "schemaName": "Payment Fraud",
            "messageClassificationName": values["message_classification"],
            "restResponseFlg": 1,
            "messageDtTm": message_datetime,
        },
        "sas": {
            "system": {
                "transactionIdentifier": transaction_identifier,
                "messageDtTmUtc": message_datetime,
            }
        },
        "customer": {
            "identifier": values["customer_identifier"],
            "surname": values["customer_surname"],
            "addressCountryCode": values["customer_country"],
            "type": values["customer_type"],
        },
        "creditcard": {
            "number": values["credit_card_number"],
            "limit": float(values["credit_card_limit"]),
            "cardholderCountryCode": values["cardholder_country"],
        },
        "transaction": {
            "transactionIdentifier": transaction_identifier,
            "amount": transaction_amount,
            "currencyCode": values["currency_code"],
            "transactionDateTime": message_datetime,
        },
        "cardfinancial": {
            "amount": card_amount,
            "usdAmount": float(values["usd_amount"]),
            "currencyCode": values["currency_code"],
            "cardPresentInd": values["card_present_ind"],
            "customerPresentInd": values["customer_present_ind"],
            "ecommerceAuthentication": values["ecommerce_authentication"],
        },
        "authentication": {
            "decision": values["auth_decision"],
            "level": values["auth_level"],
            "result": [values["auth_result"]],
            "type": values["auth_type"],
        },
        "device": {
            "identifier": values["device_identifier"],
            "fingerprint": [values["device_fingerprint"]],
            "fingerprintType": [values["device_fingerprint_type"]],
            "ipAddress": values["device_ip_address"],
        },
        "payment": {
            "debitCurrencyCode": values["currency_code"],
            "creditCurrencyCode": values["currency_code"],
            "usdAmount": float(values["usd_amount"]),
        },
        "merchant": {
            "name": values["merchant_name"],
            "categoryCode": values["merchant_category_code"],
            "country": values["merchant_country"],
        },
        "debitcard": {"number": values["debit_card_number"]},
        "debitaccount": {"number": values["debit_account_number"]},
    }

    # Rule 3 (CNP subscription testing) — only sent when the scenario tab sets it.
    subscription_identifier = values.get("subscription_identifier")
    if subscription_identifier:
        message["merchant"]["subscriptionIdentifier"] = subscription_identifier

    # Rule 6 draft (login impossible travel) — preview field, not yet a confirmed
    # SAS message shape. See docs/rules/rule_06_login_impossible_travel_DRAFT.md.
    ip_country_code = values.get("ip_country_code")
    if ip_country_code:
        message["digital"] = {"ipCountryCode": ip_country_code}

    # Rule 7 (chargeback abuse) — activityType convention is a placeholder pending
    # confirmation, see docs/rules/rule_07_refund_chargeback_abuse.md.
    chargeback_reference = values.get("chargeback_reference_number")
    if chargeback_reference:
        message["chargeback"] = {
            "referenceNumber": chargeback_reference,
            "identifier": values.get("chargeback_identifier", ""),
            "amount": float(values.get("chargeback_amount", 0) or 0),
            "merchantCurrency": values.get("currency_code", ""),
            "paymentMethod": values.get("chargeback_payment_method", ""),
            "purchaseDtTm": values.get("chargeback_purchase_dttm", ""),
            "miscellaneousData": values.get("chargeback_misc_data", ""),
        }

    return {"message": message}
