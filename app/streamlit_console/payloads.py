"""Payload builders for supported SAS message types."""

from __future__ import annotations

from typing import Any


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
