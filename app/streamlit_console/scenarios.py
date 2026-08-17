"""Registry of test scenarios for the Streamlit console.

Each scenario groups one SAS rule with the extra form tabs and readiness
checks needed to test it, so adding a new rule means adding one entry here
instead of branching app.py. See docs/rules/*.md for the SAS rule code each
scenario targets, and docs/SAS_FRAUD_RULES_CHAT_HANDOFF.md for background.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

RISKY_MCC_CANDIDATES = ["7995", "6051", "5944", "5732", "5816", "5967"]

CheckRow = dict[str, Any]
CheckFn = Callable[[dict[str, Any]], list[CheckRow]]


@dataclass(frozen=True)
class Scenario:
    key: str
    family: str
    label: str
    rule_name: str
    rule_reason: str
    status: str  # "built" | "prototype" | "draft-blocked"
    description: str
    spec_doc: str
    extra_tabs: list[str] = field(default_factory=list)
    checks: CheckFn = lambda values: []
    default_action: str = "Decline + Alert"


STATUS_LABEL = {
    "built": "Đã build & test end-to-end",
    "prototype": "Prototype — đã có SAS code, chưa deploy/tune",
    "draft-blocked": "Draft — đang chờ xác nhận trên SAS trước khi build",
}


def _cnp_new_device_checks(values: dict[str, Any]) -> list[CheckRow]:
    known_devices = [
        values.get("known_device_1", ""),
        values.get("known_device_2", ""),
        values.get("known_device_3", ""),
    ]
    device_identifier = values.get("device_identifier", "")
    return [
        {
            "Condition": "Debit card authorization",
            "Expected": "originationType = DC, activityType = CA",
            "Current": f"{values['origination_type']} / {values['activity_type']}",
            "Pass": values["origination_type"] == "DC" and values["activity_type"] == "CA",
        },
        {
            "Condition": "CNP transaction",
            "Expected": "cardPresentInd = 1",
            "Current": values["card_present_ind"],
            "Pass": values["card_present_ind"] == "1",
        },
        {
            "Condition": "High amount",
            "Expected": "cardfinancial.amount > 500",
            "Current": str(values["card_amount"]),
            "Pass": float(values["card_amount"]) > 500,
        },
        {
            "Condition": "Device identifier exists",
            "Expected": "device.identifier not blank",
            "Current": device_identifier or "(blank)",
            "Pass": bool(device_identifier),
        },
        {
            "Condition": "New device",
            "Expected": "identifier not in knownDeviceFingerprint[1..3]",
            "Current": "new" if device_identifier not in known_devices else "known",
            "Pass": bool(device_identifier) and device_identifier not in known_devices,
        },
        {
            "Condition": "Weak authentication",
            "Expected": "decision != ACCEPT or level = LOW or ecommerceAuthentication != SUCCESS",
            "Current": (
                f"{values['auth_decision']} / {values['auth_level']} / "
                f"{values['ecommerce_authentication']}"
            ),
            "Pass": (
                values["auth_decision"] != "ACCEPT"
                or values["auth_level"] == "LOW"
                or values["ecommerce_authentication"] != "SUCCESS"
            ),
        },
    ]


def _cnp_risky_mcc_checks(values: dict[str, Any]) -> list[CheckRow]:
    mcc = values.get("merchant_category_code", "")
    return [
        {
            "Condition": "Debit card authorization",
            "Expected": "originationType = DC, activityType = CA",
            "Current": f"{values['origination_type']} / {values['activity_type']}",
            "Pass": values["origination_type"] == "DC" and values["activity_type"] == "CA",
        },
        {
            "Condition": "CNP transaction",
            "Expected": "cardPresentInd = 1",
            "Current": values["card_present_ind"],
            "Pass": values["card_present_ind"] == "1",
        },
        {
            "Condition": "Amount above control threshold",
            "Expected": "cardfinancial.amount > 300",
            "Current": str(values["card_amount"]),
            "Pass": float(values["card_amount"]) > 300,
        },
        {
            "Condition": "Risky MCC",
            "Expected": f"merchant.categoryCode in {RISKY_MCC_CANDIDATES}",
            "Current": mcc or "(blank)",
            "Pass": mcc in RISKY_MCC_CANDIDATES,
        },
    ]


def _cnp_subscription_testing_checks(values: dict[str, Any]) -> list[CheckRow]:
    subscription_id = values.get("subscription_identifier", "")
    ecommerce_auth = values.get("ecommerce_authentication", "")
    return [
        {
            "Condition": "Debit card authorization",
            "Expected": "originationType = DC, activityType = CA",
            "Current": f"{values['origination_type']} / {values['activity_type']}",
            "Pass": values["origination_type"] == "DC" and values["activity_type"] == "CA",
        },
        {
            "Condition": "CNP transaction",
            "Expected": "cardPresentInd = 1",
            "Current": values["card_present_ind"],
            "Pass": values["card_present_ind"] == "1",
        },
        {
            "Condition": "Subscription identifier exists",
            "Expected": "merchant.subscriptionIdentifier not blank",
            "Current": subscription_id or "(blank)",
            "Pass": bool(subscription_id),
        },
        {
            "Condition": "Failed/attempted auth (this message)",
            "Expected": "ecommerceAuthentication in (FAILED, ATTEMPTED)",
            "Current": ecommerce_auth,
            "Pass": ecommerce_auth in ("FAILED", "ATTEMPTED"),
        },
    ]


def _structuring_checks(values: dict[str, Any]) -> list[CheckRow]:
    amount = float(values.get("card_amount", 0) or 0)
    reference_threshold = float(values.get("structuring_reference_threshold", 500) or 500)
    lower_bound = reference_threshold * 0.8
    return [
        {
            "Condition": "Debit card authorization",
            "Expected": "originationType = DC, activityType = CA",
            "Current": f"{values['origination_type']} / {values['activity_type']}",
            "Pass": values["origination_type"] == "DC" and values["activity_type"] == "CA",
        },
        {
            "Condition": "Amount near reference threshold (this message)",
            "Expected": f"[{lower_bound:.0f}, {reference_threshold:.0f}) — nhập ngưỡng tham chiếu bên tab Structuring",
            "Current": str(amount),
            "Pass": lower_bound <= amount < reference_threshold,
        },
    ]


def _device_fanout_checks(values: dict[str, Any]) -> list[CheckRow]:
    device_identifier = values.get("device_identifier", "")
    return [
        {
            "Condition": "Device identifier exists",
            "Expected": "device.identifier not blank",
            "Current": device_identifier or "(blank)",
            "Pass": bool(device_identifier),
        },
        {
            "Condition": "Profile key architecture",
            "Expected": "SAS_Device profile set keyed on device.identifier — CHƯA XÁC NHẬN",
            "Current": "unconfirmed",
            "Pass": False,
        },
    ]


def _chargeback_abuse_checks(values: dict[str, Any]) -> list[CheckRow]:
    reference_number = values.get("chargeback_reference_number", "")
    return [
        {
            "Condition": "Chargeback routing (PLACEHOLDER — cần xác nhận)",
            "Expected": "originationType = DC, activityType = CB (giả định)",
            "Current": f"{values['origination_type']} / {values['activity_type']}",
            "Pass": values["origination_type"] == "DC" and values["activity_type"] == "CB",
        },
        {
            "Condition": "Original transaction reference exists",
            "Expected": "chargeback.referenceNumber not blank",
            "Current": reference_number or "(blank)",
            "Pass": bool(reference_number),
        },
    ]


def _login_impossible_travel_checks(values: dict[str, Any]) -> list[CheckRow]:
    ip_country_code = values.get("ip_country_code", "")
    merchant_country = values.get("merchant_country", "")
    return [
        {
            "Condition": "Session country captured",
            "Expected": "digital.ipCountryCode not blank",
            "Current": ip_country_code or "(blank)",
            "Pass": bool(ip_country_code),
        },
        {
            "Condition": "Different from POS country",
            "Expected": "ipCountryCode != merchant.country",
            "Current": f"{ip_country_code or '(blank)'} vs {merchant_country or '(blank)'}",
            "Pass": bool(ip_country_code) and ip_country_code != merchant_country,
        },
        {
            "Condition": "Standalone login message support",
            "Expected": "SAS nhận message login/session riêng — CHƯA XÁC NHẬN",
            "Current": "unconfirmed",
            "Pass": False,
        },
    ]


SCENARIOS: list[Scenario] = [
    Scenario(
        key="cnp_new_device",
        family="CNP",
        label="Rule 1 — CNP + thiết bị mới + xác thực yếu",
        rule_name="rule_cnp_new_device_weak_auth",
        rule_reason="CNP_NEW_DEVICE_WEAK_AUTH",
        status="built",
        description=(
            "Từ chối + cảnh báo giao dịch CNP thẻ ghi nợ giá trị cao, phát sinh từ "
            "thiết bị mới, khi xác thực yếu/thất bại."
        ),
        spec_doc="docs/SAS_FRAUD_RULES_CHAT_HANDOFF.md",
        extra_tabs=["device_known"],
        checks=_cnp_new_device_checks,
    ),
    Scenario(
        key="cnp_risky_mcc",
        family="CNP",
        label="Rule 2 — CNP + merchant/MCC rủi ro cao",
        rule_name="rule_cnp_risky_mcc",
        rule_reason="CNP_RISKY_MCC",
        status="prototype",
        description=(
            "Cảnh báo giao dịch CNP thẻ ghi nợ khi merchant thuộc nhóm MCC rủi ro cao "
            "và số tiền vượt ngưỡng kiểm soát. Action bắt đầu là Alert-only."
        ),
        spec_doc="docs/SAS_FRAUD_RULES_CHAT_HANDOFF.md (mục 16)",
        extra_tabs=[],
        checks=_cnp_risky_mcc_checks,
        default_action="Alert only",
    ),
    Scenario(
        key="cnp_subscription_testing",
        family="CNP",
        label="Rule 3 — CNP + dò thẻ qua subscription",
        rule_name="rule_cnp_subscription_testing",
        rule_reason="CNP_SUBSCRIPTION_TESTING",
        status="prototype",
        description=(
            "Cảnh báo khi thẻ ghi nợ có 3 subscriptionIdentifier khác nhau bị từ chối/"
            "thất bại xác thực trong vòng 30 phút (dò thẻ qua kênh subscription)."
        ),
        spec_doc="docs/rules/rule_03_cnp_subscription_testing.md",
        extra_tabs=["subscription"],
        checks=_cnp_subscription_testing_checks,
        default_action="Alert only",
    ),
    Scenario(
        key="structuring",
        family="Velocity",
        label="Rule 4 — Structuring / chia nhỏ giao dịch né ngưỡng",
        rule_name="rule_cnp_structuring_threshold_split",
        rule_reason="CNP_STRUCTURING_THRESHOLD_SPLIT",
        status="prototype",
        description=(
            "Cảnh báo khi >=2 trong 5 giao dịch gần nhất đều nằm sát dưới một ngưỡng "
            "kiểm soát cố định trong 1 giờ, và tổng vượt ngưỡng đó."
        ),
        spec_doc="docs/rules/rule_04_structuring_threshold_split.md",
        extra_tabs=["structuring"],
        checks=_structuring_checks,
        default_action="Alert only",
    ),
    Scenario(
        key="device_fanout",
        family="Network",
        label="[DRAFT] Rule 5 — Device dùng chung nhiều thẻ",
        rule_name="rule_device_fanout_multi_card",
        rule_reason="DEVICE_FANOUT_MULTI_CARD",
        status="draft-blocked",
        description=(
            "1 thiết bị giao dịch trên >=3 số thẻ khác nhau trong 24h (mule device). "
            "Cần Profile Variable Set mới keyed theo device.identifier — chưa xác nhận "
            "SAS hỗ trợ."
        ),
        spec_doc="docs/rules/rule_05_device_fanout_DRAFT.md",
        extra_tabs=["device_network"],
        checks=_device_fanout_checks,
    ),
    Scenario(
        key="chargeback_abuse",
        family="Chargeback",
        label="Rule 7 — Lạm dụng chargeback (tần suất)",
        rule_name="rule_chargeback_abuse_frequency",
        rule_reason="CHARGEBACK_ABUSE_FREQUENCY",
        status="prototype",
        description=(
            "Cảnh báo khi thẻ ghi nợ có >=3 chargeback (tính cả hiện tại) trong vòng 90 "
            "ngày. Alert-only — chargeback là sự kiện đã xảy ra, không có giao dịch để "
            "Decline. Routing (activityType) đang là giả định, cần xác nhận."
        ),
        spec_doc="docs/rules/rule_07_refund_chargeback_abuse.md",
        extra_tabs=["chargeback"],
        checks=_chargeback_abuse_checks,
        default_action="Alert only",
    ),
    Scenario(
        key="login_impossible_travel",
        family="Network",
        label="[DRAFT] Rule 6 — Đăng nhập/giao dịch khác quốc gia bất khả thi",
        rule_name="rule_login_impossible_travel",
        rule_reason="LOGIN_IMPOSSIBLE_TRAVEL",
        status="draft-blocked",
        description=(
            "So khớp vị trí đăng nhập (session) với vị trí giao dịch thẻ vật lý (POS). "
            "Cần xác nhận SAS nhận message login/session riêng — chưa xác nhận."
        ),
        spec_doc="docs/rules/rule_06_login_impossible_travel_DRAFT.md",
        extra_tabs=["session"],
        checks=_login_impossible_travel_checks,
    ),
]


def scenario_by_key(key: str) -> Scenario:
    for scenario in SCENARIOS:
        if scenario.key == key:
            return scenario
    raise KeyError(f"Unknown scenario key: {key}")


def families() -> list[str]:
    seen: list[str] = []
    for scenario in SCENARIOS:
        if scenario.family not in seen:
            seen.append(scenario.family)
    return seen


def scenarios_in_family(family: str) -> list[Scenario]:
    return [scenario for scenario in SCENARIOS if scenario.family == family]
