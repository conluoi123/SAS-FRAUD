"""Application Fraud scenarios and frontend-derived risk features."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable


RULE_DISBURSEMENT = "AF_DR_Disbursement_Account_Anomaly"
RULE_REFERENCE = "AF_DR_Shared_Reference_Network"
RULE_INCOME = "AF_DR_Income_Employer_Inconsistency"
RULE_ADDRESS = "AF_DR_Linked_High_Density_Address"


@dataclass(frozen=True)
class ApplicationScenario:
    key: str
    label: str
    description: str
    expected_rules: tuple[str, ...] = ()
    expected_alert: bool = False
    verification_flags: dict[str, int] = field(default_factory=dict)
    history_kind: str = "normal"


APPLICATION_SCENARIOS: tuple[ApplicationScenario, ...] = (
    ApplicationScenario(
        key="normal",
        label="Scenario 01 — Normal, no alert",
        description="A normal synthetic loan application that should not create an alert.",
        verification_flags={
            "disbAcctOwnerMatchInd": 1,
            "employerUnverifiedInd": 0,
            "incomeMismatchInd": 0,
        },
    ),
    ApplicationScenario(
        key="shared_disbursement_account",
        label="Scenario 02 — Shared non-matching disbursement account",
        description="Another customer used the same disbursement account and ownership does not match.",
        expected_rules=(RULE_DISBURSEMENT,),
        expected_alert=True,
        verification_flags={
            "disbAcctOwnerMatchInd": 0,
            "employerUnverifiedInd": 0,
            "incomeMismatchInd": 0,
        },
        history_kind="shared_disbursement_account",
    ),
    ApplicationScenario(
        key="shared_reference_network",
        label="Scenario 03 — Shared reference network",
        description="Two other customers share the reference phone and the same synthetic cluster.",
        expected_rules=(RULE_REFERENCE,),
        expected_alert=True,
        verification_flags={
            "disbAcctOwnerMatchInd": 1,
            "employerUnverifiedInd": 0,
            "incomeMismatchInd": 0,
        },
        history_kind="shared_reference_network",
    ),
    ApplicationScenario(
        key="income_employer_inconsistency",
        label="Scenario 04 — Income and employer inconsistency",
        description="Synthetic verification flags report both an income mismatch and an unverified employer.",
        expected_rules=(RULE_INCOME,),
        expected_alert=True,
        verification_flags={
            "disbAcctOwnerMatchInd": 1,
            "employerUnverifiedInd": 1,
            "incomeMismatchInd": 1,
        },
    ),
    ApplicationScenario(
        key="linked_high_density_address",
        label="Scenario 05 — Linked high-density address",
        description="Three other customers share the normalized address; one also shares the disbursement account.",
        expected_rules=(RULE_ADDRESS,),
        expected_alert=True,
        verification_flags={
            "disbAcctOwnerMatchInd": 1,
            "employerUnverifiedInd": 0,
            "incomeMismatchInd": 0,
        },
        history_kind="linked_high_density_address",
    ),
)


def application_scenario_by_key(key: str) -> ApplicationScenario:
    for scenario in APPLICATION_SCENARIOS:
        if scenario.key == key:
            return scenario
    raise KeyError(f"Unknown Application Fraud scenario: {key}")


def normalize_address(value: str) -> str:
    """Normalize a Vietnamese address for deterministic POC comparisons."""

    decomposed = unicodedata.normalize("NFD", str(value).upper().replace("Đ", "D"))
    without_marks = "".join(
        character for character in decomposed if unicodedata.category(character) != "Mn"
    )
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9\s]", " ", without_marks)).strip()


def _utc_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        source = str(value).strip()
        if source.endswith("Z"):
            source = f"{source[:-1]}+00:00"
        parsed = datetime.fromisoformat(source)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def scenario_history(
    scenario: ApplicationScenario,
    *,
    current: dict[str, Any],
    as_of: datetime,
) -> list[dict[str, Any]]:
    """Create stable synthetic records that make each scenario hit one rule."""

    common = {
        "normalizedAddress": current["normalizedAddress"],
        "employerName": current["employerName"],
        "salesAgentIdentifier": current["salesAgentIdentifier"],
    }

    def row(index: int, **overrides: Any) -> dict[str, Any]:
        return {
            "customerIdentifier": f"CUST-HISTORY-{scenario.key.upper()}-{index}",
            "eventTime": as_of - timedelta(days=index),
            "disbAcctNumber": f"97049999{index:05d}",
            "referencePhone": f"0988000{index:03d}",
            **common,
            **overrides,
        }

    if scenario.history_kind == "shared_disbursement_account":
        return [
            row(
                1,
                disbAcctNumber=current["disbAcctNumber"],
            )
        ]
    if scenario.history_kind == "shared_reference_network":
        return [
            row(index, referencePhone=current["referencePhone"])
            for index in range(1, 3)
        ]
    if scenario.history_kind == "linked_high_density_address":
        return [
            row(
                index,
                disbAcctNumber=(
                    current["disbAcctNumber"] if index == 1 else f"97048888{index:05d}"
                ),
            )
            for index in range(1, 4)
        ]
    return []


def calculate_30d_counts(
    current: dict[str, Any],
    history: Iterable[dict[str, Any]],
    *,
    as_of: datetime,
) -> dict[str, int]:
    """Count distinct customers sharing each key in the inclusive 30-day window."""

    current_customer = str(current["customerIdentifier"])
    normalized_current = {
        **current,
        "normalizedAddress": normalize_address(str(current["normalizedAddress"])),
    }
    window_start = as_of - timedelta(days=30)
    rows: list[dict[str, Any]] = []
    for candidate in history:
        try:
            event_time = _utc_datetime(candidate.get("eventTime"))
        except (TypeError, ValueError):
            continue
        if window_start <= event_time <= as_of:
            rows.append(
                {
                    **candidate,
                    "normalizedAddress": normalize_address(
                        str(candidate.get("normalizedAddress", ""))
                    ),
                }
            )

    def customers_for(*fields: str) -> set[str]:
        customers = {current_customer}
        for row in rows:
            if all(row.get(field) == normalized_current.get(field) for field in fields):
                identifier = str(row.get("customerIdentifier", "")).strip()
                if identifier:
                    customers.add(identifier)
        return customers

    return {
        "disbAcctCustCnt30d": len(customers_for("disbAcctNumber")),
        "refPhoneCustCnt30d": len(customers_for("referencePhone")),
        "addressCustCnt30d": len(customers_for("normalizedAddress")),
        "clusterCustCnt30d": len(
            customers_for("normalizedAddress", "employerName", "salesAgentIdentifier")
        ),
    }


def expected_application_rules(app_risk: dict[str, Any]) -> list[str]:
    """Mirror the four current production rule conditions for demo comparison."""

    matched: list[str] = []
    if app_risk["disbAcctCustCnt30d"] >= 2 and app_risk["disbAcctOwnerMatchInd"] == 0:
        matched.append(RULE_DISBURSEMENT)
    if app_risk["refPhoneCustCnt30d"] >= 3 and (
        app_risk["addressCustCnt30d"] >= 4
        or app_risk["clusterCustCnt30d"] >= 3
        or app_risk["disbAcctCustCnt30d"] >= 2
    ):
        matched.append(RULE_REFERENCE)
    if app_risk["incomeMismatchInd"] == 1 and app_risk["employerUnverifiedInd"] == 1:
        matched.append(RULE_INCOME)
    if app_risk["addressCustCnt30d"] >= 4 and (
        app_risk["refPhoneCustCnt30d"] >= 3
        or app_risk["disbAcctCustCnt30d"] >= 2
        or app_risk["clusterCustCnt30d"] >= 3
    ):
        matched.append(RULE_ADDRESS)
    return matched
