"""Business-facing local alert feed for the Application Fraud demo."""

from __future__ import annotations

import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import streamlit as st

try:
    from ..alert_log import clear_alerts, load_alerts
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from alert_log import clear_alerts, load_alerts


def _rule_names(entry: dict[str, Any]) -> list[str]:
    rules = entry.get("fired_rules") or entry.get("fired_rule_identifiers") or []
    if isinstance(rules, str):
        return [rules]
    return [str(item) for item in rules if item]


def _alert_reason(entry: dict[str, Any]) -> str:
    direct = entry.get("alert_reason") or entry.get("rule_reason")
    if direct:
        return str(direct)
    for rule in entry.get("fired_rule_details") or []:
        if isinstance(rule, dict):
            reason = rule.get("alertReason") or rule.get("ruleReason")
            if reason:
                return str(reason)
    return ""


def _flatten(entry: dict[str, Any]) -> dict[str, Any]:
    """Normalize new and legacy log rows without fabricating an Alert ID."""

    rules = _rule_names(entry)
    customer = entry.get("customer_name") or entry.get("customer_identifier", "")
    return {
        "Ngày / giờ": entry.get("recorded_at", ""),
        "Alert ID": entry.get("alert_id") or "Không được trả về",
        "Application ID": entry.get("application_identifier", ""),
        "Khách hàng": customer,
        "Customer ID": entry.get("customer_identifier", ""),
        "Kênh": entry.get("channel", ""),
        "Lý do / Quy tắc": _alert_reason(entry) or ", ".join(rules),
        "Quyết định": entry.get("decision") or entry.get("outcome_name", ""),
        "Trạng thái": entry.get("alert_status")
        or ("Alert created" if entry.get("actual_alert", True) else "No alert"),
        "Transaction ID": entry.get("transaction_identifier", ""),
    }


def _recorded_date(entry: dict[str, Any]) -> date | None:
    value = entry.get("recorded_at")
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _render_detail(entry: dict[str, Any]) -> None:
    row = _flatten(entry)
    st.markdown("### Chi tiết cảnh báo")
    if entry.get("alert_id"):
        st.markdown("**Alert ID**")
        st.code(str(entry["alert_id"]), language=None)
    else:
        st.warning("Alert ID không được trả về trong runtime response hiện tại.")

    first, second, third = st.columns(3)
    first.metric("Application ID", row["Application ID"] or "—")
    second.metric("Khách hàng", row["Khách hàng"] or "—")
    third.metric("Kênh", row["Kênh"] or "—")
    st.markdown("**Lý do cảnh báo**")
    st.write(_alert_reason(entry) or "SAS không trả về alertReason/ruleReason.")
    st.markdown("**Quy tắc phát hiện**")
    rules = _rule_names(entry)
    st.write(", ".join(rules) if rules else "Không có tên quy tắc trong log.")
    evidence = entry.get("evidence") or []
    if evidence:
        st.markdown("**Bằng chứng / Dấu hiệu rủi ro**")
        st.dataframe(evidence, use_container_width=True, hide_index=True)
    st.caption(
        f"Transaction ID: {row['Transaction ID'] or '—'} · "
        f"Thời điểm xử lý: {row['Ngày / giờ'] or '—'}"
    )
    with st.expander("Chi tiết kỹ thuật", expanded=False):
        st.json(entry, expanded=False)


def main() -> None:
    bank_name = os.getenv("BANK_DISPLAY_NAME", "Demo Bank")
    st.set_page_config(
        page_title=f"{bank_name} | Nhật ký cảnh báo",
        page_icon="🔔",
        layout="wide",
    )
    st.markdown(
        "<style>[data-testid='stSidebarNav']{display:none}</style>",
        unsafe_allow_html=True,
    )
    with st.sidebar:
        st.markdown(f"### {bank_name}")
        st.caption("Loan Origination & Fraud Screening")
        st.markdown(
            """
            <div style="display:grid;gap:.35rem;margin:.8rem 0 1rem 0">
              <a href="/" target="_self" style="text-decoration:none;color:#17324d;padding:.55rem .7rem;border-radius:7px;background:#f1f5f9">🏦 Hồ sơ mới / Xử lý hàng loạt</a>
              <a href="/Alert_Log" target="_self" style="text-decoration:none;color:#17324d;padding:.55rem .7rem;border-radius:7px;background:#e7eef6;font-weight:650">🔔 Nhật ký cảnh báo</a>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()
        st.caption("Demo / Synthetic Data · POC")

    st.markdown(f"### {bank_name}")
    st.title("Nhật ký cảnh báo")
    st.caption(
        "Cảnh báo phát sinh từ các lần sàng lọc hồ sơ trong portal. Đây là local demo log; "
        "không phải workflow điều tra hoặc disposition."
    )

    alerts = load_alerts()
    app_alerts = [
        item
        for item in alerts
        if item.get("fraud_domain") == "Application Fraud"
        or item.get("schema_name") == "Application Fraud"
        or item.get("application_identifier")
    ]
    display_alerts = app_alerts or alerts
    metrics = st.columns(3)
    metrics[0].metric("Tổng cảnh báo", len(display_alerts))
    metrics[1].metric(
        "Có Alert ID", sum(bool(item.get("alert_id")) for item in display_alerts)
    )
    metrics[2].metric(
        "Quy tắc khác nhau",
        len({rule for item in display_alerts for rule in _rule_names(item)}),
    )

    if not display_alerts:
        st.info("Chưa có cảnh báo nào được ghi nhận trong local demo log.")
        return

    st.markdown("#### Bộ lọc")
    dates = [value for item in display_alerts if (value := _recorded_date(item))]
    first, second, third = st.columns(3)
    start_date = first.date_input(
        "Từ ngày", value=min(dates) if dates else date.today()
    )
    end_date = second.date_input(
        "Đến ngày", value=max(dates) if dates else date.today()
    )
    channels = sorted(
        {str(item.get("channel")) for item in display_alerts if item.get("channel")}
    )
    channel = third.selectbox("Kênh", ["Tất cả", *channels])
    fourth, fifth, sixth = st.columns(3)
    alert_query = fourth.text_input("Alert ID")
    application_query = fifth.text_input("Application ID")
    customer_query = sixth.text_input("Khách hàng / Customer ID")
    rule_query = st.text_input("Quy tắc / Lý do")

    filtered: list[dict[str, Any]] = []
    for item in display_alerts:
        item_date = _recorded_date(item)
        haystack_rule = f"{_alert_reason(item)} {' '.join(_rule_names(item))}".lower()
        customer_text = f"{item.get('customer_name', '')} {item.get('customer_identifier', '')}".lower()
        if item_date and not (start_date <= item_date <= end_date):
            continue
        if channel != "Tất cả" and item.get("channel") != channel:
            continue
        if alert_query.lower() not in str(item.get("alert_id") or "").lower():
            continue
        if (
            application_query.lower()
            not in str(item.get("application_identifier") or "").lower()
        ):
            continue
        if customer_query.lower() not in customer_text:
            continue
        if rule_query.lower() not in haystack_rule:
            continue
        filtered.append(item)

    st.markdown(f"#### Danh sách cảnh báo ({len(filtered)})")
    st.dataframe(
        [_flatten(item) for item in filtered], use_container_width=True, hide_index=True
    )
    if filtered:
        labels = [
            f"{item.get('application_identifier') or 'Không có Application ID'} · "
            f"{item.get('alert_id') or 'Alert ID chưa được trả về'}"
            for item in filtered
        ]
        selected = st.selectbox("Mở chi tiết", labels)
        _render_detail(filtered[labels.index(selected)])

    with st.expander("Quản trị local demo log", expanded=False):
        st.warning("Thao tác này xóa toàn bộ bản ghi local và không thể hoàn tác.")
        confirmed = st.checkbox("Tôi hiểu và muốn xóa local demo log")
        if st.button("Xóa local demo log", disabled=not confirmed):
            clear_alerts()
            st.rerun()


if __name__ == "__main__":
    main()
