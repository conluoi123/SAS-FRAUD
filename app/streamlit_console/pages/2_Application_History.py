"""Business-facing processed loan application history."""

from __future__ import annotations

import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import streamlit as st

try:
    from ..application_history import load_application_history
    from ..copy_control import render_copyable_value
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from application_history import load_application_history
    from copy_control import render_copyable_value


def _processed_date(entry: dict[str, Any]) -> date | None:
    value = entry.get("processed_at")
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _rule_names(entry: dict[str, Any]) -> list[str]:
    rules = entry.get("fired_rules") or []
    if isinstance(rules, str):
        return [rules]
    return [str(rule) for rule in rules if rule]


def _alerted_entities(entry: dict[str, Any]) -> list[dict[str, str]]:
    raw = entry.get("alerted_entities") or []
    if isinstance(raw, dict):
        raw = [raw]
    entities = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        entity = item.get("alerted_entity") or item.get("outcomeEntity")
        entity_type = item.get("alerted_entity_type") or item.get("outcomeEntityType")
        if entity or entity_type:
            entities.append(
                {
                    "alerted_entity": str(entity or ""),
                    "alerted_entity_type": str(entity_type or ""),
                }
            )
    return entities


def _fraud_result(entry: dict[str, Any]) -> str:
    if entry.get("request_status") != "Request successful":
        return "Failed"
    return "Alert" if entry.get("alert_created") else "No Alert"


def _money(amount: Any, currency: Any) -> str:
    if isinstance(amount, (int, float)) and not isinstance(amount, bool):
        return f"{amount:,.0f} {currency or ''}".strip()
    return f"{amount or '—'} {currency or ''}".strip()


def _table_row(entry: dict[str, Any]) -> dict[str, Any]:
    entities = _alerted_entities(entry)
    return {
        "Processed Time": entry.get("processed_at", ""),
        "Application ID": entry.get("application_id", ""),
        "Customer": entry.get("customer_name") or entry.get("customer_id", ""),
        "Channel": entry.get("channel", ""),
        "Product": entry.get("application_type", ""),
        "Amount": _money(entry.get("requested_amount"), entry.get("currency")),
        "Fraud Result": _fraud_result(entry),
        "Triggered Rule": ", ".join(_rule_names(entry)) or "—",
        "Alerted Entity": " | ".join(
            item["alerted_entity"] for item in entities if item["alerted_entity"]
        )
        or "—",
        "Status": entry.get("request_status", ""),
    }


def _render_detail(entry: dict[str, Any]) -> None:
    st.markdown("### Chi tiết hồ sơ")

    st.markdown("#### Thông tin hồ sơ")
    first, second, third, fourth = st.columns(4)
    with first:
        render_copyable_value("Application ID", entry.get("application_id"))
    second.metric("Sản phẩm", entry.get("application_type") or "—")
    third.metric(
        "Số tiền đề nghị",
        _money(entry.get("requested_amount"), entry.get("currency")),
    )
    fourth.metric("Kênh", entry.get("channel") or "—")

    st.markdown("#### Thông tin khách hàng")
    customer_columns = st.columns(3)
    customer_columns[0].metric("Customer ID", entry.get("customer_id") or "—")
    customer_columns[1].metric("Khách hàng", entry.get("customer_name") or "—")
    customer_columns[2].metric("Applicant ID", entry.get("applicant_id") or "—")

    st.markdown("#### Kết quả sàng lọc")
    result_columns = st.columns(3)
    result_columns[0].metric("Fraud Result", _fraud_result(entry))
    result_columns[1].metric("Trạng thái", entry.get("request_status") or "—")
    result_columns[2].metric("Decision / Outcome", entry.get("decision") or "—")

    st.markdown("**Triggered rules**")
    rules = _rule_names(entry)
    st.write(", ".join(rules) if rules else "Không có quy tắc nào được kích hoạt.")
    if entry.get("alert_reason"):
        st.markdown("**Alert reason**")
        st.write(entry["alert_reason"])
    evidence = entry.get("evidence") or []
    if evidence:
        st.markdown("**Evidence**")
        st.dataframe(
            [
                {
                    "Bằng chứng / Dấu hiệu": item.get("label")
                    or item.get("type")
                    or "—",
                    "Giá trị": item.get("value", "—"),
                }
                for item in evidence
            ],
            use_container_width=True,
            hide_index=True,
        )

    entities = _alerted_entities(entry)
    if entry.get("alert_created") and entities:
        st.markdown("#### Thực thể cảnh báo")
        for index, item in enumerate(entities, start=1):
            if len(entities) > 1:
                st.caption(f"Thực thể {index}")
            if item["alerted_entity"]:
                render_copyable_value("Alerted Entity", item["alerted_entity"])
            st.markdown(f"**Entity Type:** `{item['alerted_entity_type'] or '—'}`")
        st.caption("Sử dụng thực thể này để tra cứu trong SAS Alert Triage.")

    render_copyable_value("Transaction ID", entry.get("transaction_id"))

    with st.expander("Chi tiết kỹ thuật", expanded=False):
        technical = st.columns(3)
        technical[0].metric("HTTP status", entry.get("http_status") or "—")
        technical[1].metric(
            "Duration",
            (
                f"{entry['processing_duration_ms']} ms"
                if entry.get("processing_duration_ms") is not None
                else "—"
            ),
        )
        technical[2].metric("Source", entry.get("source") or "—")
        if entry.get("message_id"):
            render_copyable_value("Message ID", entry.get("message_id"))
        request_tab, response_tab, rules_tab = st.tabs(
            ["Request JSON", "SAS Response", "Raw rule fields"]
        )
        with request_tab:
            st.json(entry.get("request_json"), expanded=False)
        with response_tab:
            if entry.get("parsed_response") is not None:
                st.json(entry["parsed_response"], expanded=False)
            elif entry.get("raw_response"):
                st.code(entry["raw_response"], language="text", wrap_lines=True)
            else:
                st.info(entry.get("error_message") or "Không có SAS response.")
        with rules_tab:
            st.json(entry.get("fired_rule_details") or [], expanded=False)


def main() -> None:
    bank_name = os.getenv("BANK_DISPLAY_NAME", "Demo Bank")
    st.set_page_config(
        page_title=f"{bank_name} | Hồ sơ đã xử lý",
        page_icon="📋",
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
              <a href="/Application_History" target="_self" style="text-decoration:none;color:#17324d;padding:.55rem .7rem;border-radius:7px;background:#e7eef6;font-weight:650">📋 Hồ sơ đã xử lý</a>
              <a href="/Alert_Log" target="_self" style="text-decoration:none;color:#17324d;padding:.55rem .7rem;border-radius:7px;background:#f1f5f9">🔔 Nhật ký cảnh báo</a>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()
        st.caption("Demo / Synthetic Data · POC")

    st.markdown(f"### {bank_name}")
    st.title("Hồ sơ đã xử lý")
    st.caption(
        "Application History lưu tất cả hồ sơ vay đã thực sự gửi để sàng lọc. "
        "Nhật ký cảnh báo là khu vực riêng và chỉ chứa các fraud alert."
    )

    history = load_application_history()
    if not history:
        st.info("Chưa có hồ sơ nào được xử lý trong local Application History.")
        return

    metrics = st.columns(3)
    metrics[0].metric("Tổng hồ sơ", len(history))
    metrics[1].metric(
        "Có cảnh báo", sum(bool(item.get("alert_created")) for item in history)
    )
    metrics[2].metric(
        "Xử lý thành công",
        sum(item.get("request_status") == "Request successful" for item in history),
    )

    st.markdown("#### Bộ lọc")
    dates = [value for item in history if (value := _processed_date(item))]
    first, second, third = st.columns(3)
    start_date = first.date_input(
        "Từ ngày", value=min(dates) if dates else date.today()
    )
    end_date = second.date_input(
        "Đến ngày", value=max(dates) if dates else date.today()
    )
    channels = sorted(
        {str(item.get("channel")) for item in history if item.get("channel")}
    )
    channel = third.selectbox("Kênh", ["Tất cả", *channels])

    fourth, fifth, sixth = st.columns(3)
    application_query = fourth.text_input("Application ID")
    customer_query = fifth.text_input("Khách hàng / Customer ID")
    result_filter = sixth.selectbox(
        "Kết quả", ["Tất cả", "Alert", "No Alert", "Failed"]
    )
    rule_query = st.text_input("Quy tắc / Lý do")

    filtered = []
    for item in history:
        item_date = _processed_date(item)
        if item_date and not (start_date <= item_date <= end_date):
            continue
        if channel != "Tất cả" and item.get("channel") != channel:
            continue
        if (
            application_query.lower()
            not in str(item.get("application_id") or "").lower()
        ):
            continue
        customer_text = (
            f"{item.get('customer_id', '')} {item.get('customer_name', '')}".lower()
        )
        if customer_query.lower() not in customer_text:
            continue
        if result_filter != "Tất cả" and _fraud_result(item) != result_filter:
            continue
        rule_text = (
            f"{' '.join(_rule_names(item))} {item.get('alert_reason', '')}".lower()
        )
        if rule_query.lower() not in rule_text:
            continue
        filtered.append(item)

    st.markdown(f"#### Danh sách hồ sơ ({len(filtered)})")
    st.dataframe(
        [_table_row(item) for item in filtered],
        use_container_width=True,
        hide_index=True,
    )
    if filtered:
        labels = [
            f"{item.get('application_id') or 'Không có Application ID'} · "
            f"{item.get('customer_name') or item.get('customer_id') or 'Không có khách hàng'}"
            for item in filtered
        ]
        selected = st.selectbox("Mở chi tiết hồ sơ", labels)
        _render_detail(filtered[labels.index(selected)])


if __name__ == "__main__":
    main()
