"""Quick Alert Demo scenarios for Application Fraud.

Each demo sends a short, real sequence of Application Fraud messages built with
build_application_fraud_payload() and delivered through send_message(). No demo
here invents SAS output: profile counts such as disbAcctCustCnt30d,
refPhoneCustCnt30d, addressCustCnt30d, and clusterCustCnt30d are never computed
or sent by the frontend — SAS Profiles own those windows, and the actual fired
rules shown to the presenter always come from the real response.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import sleep
from typing import Any, Callable

try:
    from .application_scenarios import RULE_ADDRESS, RULE_DISBURSEMENT, RULE_REFERENCE
    from .payloads import build_application_fraud_payload, validate_application_fraud_payload
    from .sas_client import SasRuntimeResponse, send_message
except ImportError:
    from application_scenarios import RULE_ADDRESS, RULE_DISBURSEMENT, RULE_REFERENCE
    from payloads import build_application_fraud_payload, validate_application_fraud_payload
    from sas_client import SasRuntimeResponse, send_message


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _suffix() -> str:
    return uuid.uuid4().hex[:8].upper()


def _digits(length: int) -> str:
    """Return numeric-only synthetic data for phone, ID and account fields."""

    return "".join(str(int(character, 16) % 10) for character in uuid.uuid4().hex[:length])


def _sequence_timestamps(values: list[dict[str, Any]]) -> None:
    """Give demo messages increasing UTC times without placing them in the future."""

    started = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(
        seconds=max(0, len(values) - 1)
    )
    for index, item in enumerate(values):
        item["message_datetime"] = (
            (started + timedelta(seconds=index))
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )


def _default_app_risk(prefix: str) -> dict[str, Any]:
    suffix = _suffix()
    return {
        "bankId": "BANK-DEMO",
        "salesAgentIdentifier": f"SALES-DEMO-{prefix}-{suffix}",
        "disbAcctNumber": _digits(14),
        "referencePhone": f"09{_digits(8)}",
        "normalizedAddress": f"{suffix} DEMO STREET, DEMO DISTRICT",
        "disbAcctOwnerMatchInd": 1,
        "employerUnverifiedInd": 0,
    }


def _base_values(prefix: str, **overrides: Any) -> dict[str, Any]:
    suffix = _suffix()
    values: dict[str, Any] = {
        "message_datetime": _now_iso(),
        "application_identifier": f"APP-DEMO-{prefix}-{suffix}",
        "transaction_identifier": f"MSG-DEMO-{prefix}-{suffix}",
        "application_type": "PERSONAL_LOAN",
        "application_amount": 50_000_000.0,
        "currency_code": "VND",
        "application_channel": "MOBILE_APP",
        "application_purpose": "PERSONAL_USE",
        "application_status": "SUBMITTED",
        "application_stage": "UNDER_REVIEW",
        "applicant_identifier": f"APL-DEMO-{prefix}-{suffix}",
        "applicant_name": "Demo Applicant",
        "monthly_regular_income": 25_000_000.0,
        "outstanding_debt": 5_000_000.0,
        "employer_name": "Demo Company",
        "employment_status": "EMPLOYED",
        "customer_identifier": f"CUST-DEMO-{prefix}-{suffix}",
        "customer_name": "Demo Applicant",
        "customer_type": "INDIVIDUAL",
        "address_country_code": "VN",
        "identification_number": _digits(12),
        "email": f"demo.{suffix.lower()}@example.com",
        "phone": f"09{_digits(8)}",
        "months_at_location": 24,
        "device_identifier": f"DEV-DEMO-{prefix}-{suffix}",
        "device_ip_address": "203.0.113.42",
    }
    values.update(overrides)
    return values


@dataclass(frozen=True)
class DemoStep:
    label: str
    values: dict[str, Any]


@dataclass(frozen=True)
class DemoSpec:
    key: str
    title: str
    target_rule: str
    build_steps: Callable[[], list[DemoStep]]
    no_hit_message: str
    intro: str = ""


def build_demo1_steps() -> list[DemoStep]:
    """Shared disbursement account, owner mismatch on the second application."""

    shared_account = _digits(14)

    seed_values = _base_values("D1A")
    seed_values["app_risk"] = {
        **_default_app_risk("D1A"),
        "disbAcctNumber": shared_account,
        "disbAcctOwnerMatchInd": 1,
    }

    trigger_values = _base_values("D1B")
    trigger_values["app_risk"] = {
        **_default_app_risk("D1B"),
        "disbAcctNumber": shared_account,
        "disbAcctOwnerMatchInd": 0,
    }

    values = [seed_values, trigger_values]
    _sequence_timestamps(values)
    return [
        DemoStep("Seed A - account owner matches", seed_values),
        DemoStep("Trigger B - shared account, owner mismatch", trigger_values),
    ]


def build_demo2_steps() -> list[DemoStep]:
    """Three customers sharing one reference phone; two also share an account."""

    shared_phone = f"09{_digits(8)}"
    account_x = _digits(14)
    account_y = _digits(14)

    values_a = _base_values("D2A")
    values_a["app_risk"] = {
        **_default_app_risk("D2A"),
        "referencePhone": shared_phone,
        "disbAcctNumber": account_x,
    }
    values_b = _base_values("D2B")
    values_b["app_risk"] = {
        **_default_app_risk("D2B"),
        "referencePhone": shared_phone,
        "disbAcctNumber": account_y,
    }
    values_c = _base_values("D2C")
    values_c["app_risk"] = {
        **_default_app_risk("D2C"),
        "referencePhone": shared_phone,
        "disbAcctNumber": account_x,
    }

    values = [values_a, values_b, values_c]
    _sequence_timestamps(values)
    return [
        DemoStep("A - shared reference phone", values_a),
        DemoStep("B - shared reference phone", values_b),
        DemoStep("C trigger - shared phone and account with A", values_c),
    ]


def build_demo3_steps() -> list[DemoStep]:
    """Four customers sharing address, employer, and sales agent."""

    shared_address = f"{_suffix()} DEMO CLUSTER STREET, DEMO DISTRICT"
    shared_employer = "Demo Cluster Company"
    shared_agent = f"SALES-DEMO-CLUSTER-{_suffix()}"

    steps: list[DemoStep] = []
    for label, prefix in (("A", "D3A"), ("B", "D3B"), ("C", "D3C"), ("D trigger", "D3D")):
        values = _base_values(prefix, employer_name=shared_employer)
        values["app_risk"] = {
            **_default_app_risk(prefix),
            "normalizedAddress": shared_address,
            "salesAgentIdentifier": shared_agent,
        }
        steps.append(DemoStep(label, values))
    _sequence_timestamps([step.values for step in steps])
    return steps


DEMO_SPECS: dict[str, DemoSpec] = {
    "demo1": DemoSpec(
        key="demo1",
        title="Run Shared Account Alert",
        target_rule=RULE_DISBURSEMENT,
        build_steps=build_demo1_steps,
        no_hit_message=(
            "SAS did not return this rule. Check AF_DisbursementAccount "
            "and its Variable Rule."
        ),
        intro="Sends two customers with one disbursement account; the trigger has an owner mismatch.",
    ),
    "demo2": DemoSpec(
        key="demo2",
        title="Run Reference Network Alert",
        target_rule=RULE_REFERENCE,
        build_steps=build_demo2_steps,
        no_hit_message=(
            "SAS did not return this rule. Check AF_ReferencePhone "
            "and the linked-condition threshold."
        ),
        intro="Sends three customers with one reference phone; two also share a disbursement account.",
    ),
    "demo3": DemoSpec(
        key="demo3",
        title="Run Linked Address Alert",
        target_rule=RULE_ADDRESS,
        build_steps=build_demo3_steps,
        no_hit_message=(
            "SAS did not return this rule. Check AF_Address and the shared "
            "address, employer and sales-agent conditions."
        ),
        intro="Sends four customers with one normalized address, employer and sales agent.",
    ),
}


def run_demo_steps(
    steps: list[DemoStep],
    *,
    endpoint: str,
    timeout_seconds: float,
    verify_tls: bool,
    ca_bundle: str | None,
    sender: Callable[..., SasRuntimeResponse] = send_message,
    delay_seconds: float = 0.5,
    sleeper: Callable[[float], None] = sleep,
) -> list[dict[str, Any]]:
    """Send each step strictly in order; stop as soon as one is not HTTP 2xx."""

    results: list[dict[str, Any]] = []
    for step in steps:
        payload = build_application_fraud_payload(step.values)
        errors = validate_application_fraud_payload(payload)
        entry: dict[str, Any] = {
            "label": step.label,
            "payload": payload,
            "response": None,
            "errors": errors,
        }
        if errors:
            results.append(entry)
            break
        response = sender(
            endpoint=endpoint,
            payload=payload,
            timeout_seconds=timeout_seconds,
            verify_tls=verify_tls,
            ca_bundle=ca_bundle,
        )
        entry["response"] = response
        results.append(entry)
        if not (200 <= response.status_code < 300):
            break
        if step is not steps[-1] and delay_seconds > 0:
            sleeper(delay_seconds)
    return results
