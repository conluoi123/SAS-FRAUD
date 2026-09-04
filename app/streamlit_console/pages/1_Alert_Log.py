"""Alert Log — mức 1: xem tích lũy các alert đã phát sinh từ console gửi message.

Không gộp case, không disposition — đó là việc của Investigator (mức 2, để sau).
"""

from __future__ import annotations

import streamlit as st

try:
    from ..alert_log import clear_alerts, load_alerts
except ImportError:
    # Streamlit executes this file as a standalone script, not as part of a package.
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from alert_log import clear_alerts, load_alerts


def _flatten(entry: dict) -> dict:
    entities = entry.get("alerted_entities") or []
    entity_text = ", ".join(
        f"{item.get('outcomeEntity', '')} ({item.get('outcomeEntityType', '')})"
        for item in entities
        if isinstance(item, dict)
    )
    rules = entry.get("fired_rules") or entry.get("fired_rule_identifiers") or []
    return {
        "Recorded at (UTC)": entry.get("recorded_at", ""),
        "Domain": entry.get("fraud_domain", entry.get("domain", "Payment Fraud")),
        "Schema": entry.get("schema_name", "Payment Fraud"),
        "Scenario": entry.get("scenario_label", ""),
        "Rule name": entry.get("rule_name", ""),
        "Rule reason": entry.get("rule_reason", ""),
        "Outcome": entry.get("outcome_name", ""),
        "Entity": entity_text,
        "Fired rule IDs": ", ".join(str(r) for r in rules if r),
        "Transaction": entry.get("transaction_identifier", ""),
        "Application": entry.get("application_identifier", ""),
        "Customer": entry.get("customer_identifier", ""),
        "Expected alert": entry.get("expected_alert", ""),
        "Actual alert": entry.get("actual_alert", ""),
        "Expected rules": ", ".join(entry.get("expected_rules") or []),
        "HTTP status": entry.get("http_status", ""),
        "Message ID": entry.get("message_identifier", ""),
    }


def main() -> None:
    st.set_page_config(page_title="Alert Log", page_icon="S", layout="wide")
    st.title("Alert Log")
    st.caption(
        "Danh sách tích lũy các alert đã phát sinh khi gửi message qua console "
        "(trang 'SAS Fraud Console'). Đây là bản ghi log đơn giản — mức 1, không gộp "
        "case/disposition (dự kiến làm sau, xem docs/investigator_scenarios/)."
    )

    alerts = load_alerts()

    first, second = st.columns(2)
    first.metric("Tổng số alert đã ghi", len(alerts))
    by_rule: dict[str, int] = {}
    for entry in alerts:
        rule_name = entry.get("rule_name", "unknown")
        by_rule[rule_name] = by_rule.get(rule_name, 0) + 1
    second.metric("Số rule khác nhau đã fire", len(by_rule))

    if by_rule:
        st.markdown("**Theo rule:**")
        st.dataframe(
            [
                {"Rule": rule, "Số lần fire": count}
                for rule, count in sorted(by_rule.items())
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    if not alerts:
        st.info(
            "Chưa có alert nào được ghi. Gửi 1 message trigger ở trang console để xem."
        )
    else:
        st.dataframe(
            [_flatten(entry) for entry in alerts],
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("Xem raw JSON từng alert"):
            st.json(alerts, expanded=False)

    st.divider()
    if st.button("Xóa toàn bộ log (reset trước demo)", icon=":material/delete:"):
        clear_alerts()
        st.rerun()


if __name__ == "__main__":
    main()
