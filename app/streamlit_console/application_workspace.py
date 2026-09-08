"""Operational Streamlit workspace for Application Fraud only."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

import requests
import streamlit as st

try:
    from .alert_log import record_alert
    from .application_batch import (
        RESULT_COLUMNS,
        application_csv_template,
        claim_batch_run,
        execute_application_batch,
        finish_batch_run,
        invalid_batch_results,
        parse_application_csv,
        reset_batch_for_new_file,
        results_to_csv,
    )
    from .application_config import (
        AF_CIC_PROFILE_CAPACITY,
        APPLICATION_ACTIVITY_TYPE,
        APPLICATION_AUTHENTICATION_TYPE,
        APPLICATION_CHANNELS,
        APPLICATION_CUSTOMER_TYPE,
        APPLICATION_ORIGINATION_TYPE,
    )
    from .payloads import (
        build_application_fraud_payload,
        validate_application_fraud_payload,
    )
    from .sas_client import SasRuntimeResponse, send_message
    from .sas_response import extract_return_fields, summarize_sas_response
except ImportError:
    from alert_log import record_alert
    from application_batch import (
        RESULT_COLUMNS,
        application_csv_template,
        claim_batch_run,
        execute_application_batch,
        finish_batch_run,
        invalid_batch_results,
        parse_application_csv,
        reset_batch_for_new_file,
        results_to_csv,
    )
    from application_config import (
        AF_CIC_PROFILE_CAPACITY,
        APPLICATION_ACTIVITY_TYPE,
        APPLICATION_AUTHENTICATION_TYPE,
        APPLICATION_CHANNELS,
        APPLICATION_CUSTOMER_TYPE,
        APPLICATION_ORIGINATION_TYPE,
    )
    from payloads import (
        build_application_fraud_payload,
        validate_application_fraud_payload,
    )
    from sas_client import SasRuntimeResponse, send_message
    from sas_response import extract_return_fields, summarize_sas_response


ALERT_TYPE_CODE = "app_fraud_app"
ALERT_ENTITY_TYPE = "sfd_application"


def _new_application_id() -> str:
    return f"APP-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def _new_transaction_id() -> str:
    return f"MSG-{uuid.uuid4().hex[:16].upper()}"


def _initialize_state() -> None:
    defaults = {
        "af_single_application_id": _new_application_id(),
        "af_single_transaction_id": _new_transaction_id(),
        "af_single_sending": False,
        "af_single_last_transaction": None,
        "af_single_result": None,
        "af_batch_fingerprint": None,
        "af_batch_validation": None,
        "af_batch_validated_rows": [],
        "af_batch_validation_errors": [],
        "af_batch_status": "idle",
        "af_batch_progress": 0,
        "af_batch_results": [],
        "af_batch_details": {},
        "af_batch_running": False,
        "af_batch_completed_fingerprint": None,
        "af_batch_filter": "Tất cả",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _render_styles() -> None:
    st.markdown(
        """
        <style>
        .af-console-header {
            background: #f7f9fc;
            border: 1px solid #d8dee8;
            border-left: 4px solid #17365d;
            border-radius: 4px;
            padding: 16px 18px;
            margin: 0 0 16px 0;
        }
        .af-console-header h2 { color: #17365d; font-size: 1.35rem; margin: 0; }
        .af-console-header p { color: #4b5563; margin: 5px 0 0 0; }
        .af-section-title {
            color: #17365d;
            font-size: 1rem;
            font-weight: 650;
            border-bottom: 1px solid #d8dee8;
            padding-bottom: 6px;
            margin: 6px 0 10px 0;
        }
        .af-contract-note {
            background: #f7f9fc;
            border: 1px solid #d8dee8;
            border-radius: 3px;
            color: #374151;
            padding: 10px 12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _section(title: str) -> None:
    st.markdown(f'<div class="af-section-title">{title}</div>', unsafe_allow_html=True)


def _utc_string(selected_date: Any, selected_time: Any) -> str:
    return (
        datetime.combine(selected_date, selected_time, tzinfo=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _rule_flags(response: SasRuntimeResponse) -> tuple[bool, bool, list[str]]:
    if not isinstance(response.parsed_body, dict):
        return False, False, []
    message = response.parsed_body.get("message", {})
    sas = message.get("sas", {}) if isinstance(message, dict) else {}
    rules = sas.get("rulefired", []) if isinstance(sas, dict) else []
    rules = rules if isinstance(rules, list) else ([rules] if isinstance(rules, dict) else [])

    def flag(value: Any) -> bool:
        return (
            value.strip().lower() in {"1", "true", "yes", "y"}
            if isinstance(value, str)
            else bool(value)
        )

    fired = [rule for rule in rules if isinstance(rule, dict) and flag(rule.get("firedFlg"))]
    names = [
        str(
            rule.get("ruleIdentifier")
            or rule.get("ruleName")
            or rule.get("ruleReference")
            or ""
        )
        for rule in fired
    ]
    alert = summarize_sas_response(response.parsed_body).alert_created
    return bool(fired), alert, [name for name in names if name]


def _record_alert_if_created(payload: dict[str, Any], response: SasRuntimeResponse) -> None:
    fired, alert, rules = _rule_flags(response)
    if not alert:
        return
    message = payload["message"]
    summary = summarize_sas_response(response.parsed_body)
    record_alert(
        {
            "recorded_at": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "fraud_domain": "Application Fraud",
            "schema_name": "Application Fraud",
            "alert_type": ALERT_TYPE_CODE,
            "application_identifier": message["application"]["identifier"],
            "customer_identifier": message["customer"]["identifier"],
            "transaction_identifier": message["sas"]["system"]["transactionIdentifier"],
            "actual_alert": alert,
            "fired_rules": rules,
            "fired_rule_identifiers": rules,
            "http_status": response.status_code,
            "outcome_name": summary.outcome_name,
            "alerted_entities": summary.alerted_entities,
            "rule_fired": fired,
        }
    )


def _render_single_result(result: dict[str, Any]) -> None:
    response: SasRuntimeResponse = result["response"]
    payload: dict[str, Any] = result["payload"]
    return_fields = extract_return_fields(response.parsed_body)
    summary = (
        summarize_sas_response(response.parsed_body)
        if response.parsed_body is not None
        else None
    )
    fired, alert, rules = _rule_flags(response)
    request_ok = 200 <= response.status_code < 300 and response.parse_error is None

    _section("Kết quả xử lý")
    status_columns = st.columns(3)
    status_columns[0].metric(
        "Request", "Thành công" if request_ok else "Gửi thất bại"
    )
    status_columns[1].metric("Rule", "Đã fire" if fired else "Không fire")
    status_columns[2].metric("Alert", "Đã tạo" if alert else "Không cảnh báo")

    detail_columns = st.columns(4)
    detail_columns[0].metric("HTTP status", response.status_code)
    detail_columns[1].metric("Thời gian xử lý", f"{response.elapsed_ms} ms")
    detail_columns[2].metric("returnType", return_fields.get("returnType"))
    detail_columns[3].metric(
        "Decision",
        (summary.outcome_name or summary.outcome) if summary else "—",
    )
    st.write("Rule đã fire:", ", ".join(rules) if rules else "Không có")
    if return_fields.get("returnDesc") or return_fields.get("returnDetails"):
        st.caption(
            " | ".join(
                str(value)
                for value in (
                    return_fields.get("returnDesc"),
                    return_fields.get("returnDetails"),
                )
                if value is not None
            )
        )
    profiles = (
        response.parsed_body.get("profiles")
        if isinstance(response.parsed_body, dict)
        else None
    )
    if profiles is not None:
        with st.expander("Profile trả về", expanded=False):
            st.json(profiles, expanded=False)
    with st.expander("Chi tiết phản hồi", expanded=False):
        if response.parse_error:
            st.error(f"Invalid JSON response: {response.parse_error}")
        st.code(response.raw_body, language="text", wrap_lines=True)
    with st.expander("Request JSON", expanded=False):
        st.json(payload, expanded=False)

    if st.button("Tạo hồ sơ mới", key="af_new_single", use_container_width=True):
        st.session_state["af_single_application_id"] = _new_application_id()
        st.session_state["af_single_transaction_id"] = _new_transaction_id()
        st.session_state["af_single_last_transaction"] = None
        st.session_state["af_single_result"] = None
        st.rerun()


def _render_single(
    *, endpoint: str, timeout_seconds: float, verify_tls: bool, ca_bundle: str | None
) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    channel_codes = list(APPLICATION_CHANNELS)
    with st.form("af_single_form", border=True):
        _section("1. Thông tin hồ sơ")
        first, second = st.columns(2)
        application_identifier = first.text_input(
            "Mã hồ sơ", value=st.session_state["af_single_application_id"]
        )
        application_type = second.selectbox(
            "Sản phẩm vay", ["PERSONAL_LOAN", "HOME_LOAN", "AUTO_LOAN"]
        )
        application_amount = first.number_input(
            "Số tiền đề nghị", min_value=0.0, value=50_000_000.0, step=1_000_000.0
        )
        currency_code = second.selectbox("Loại tiền", ["VND", "USD"])
        application_purpose = first.selectbox(
            "Mục đích vay", ["PERSONAL_USE", "HOME_RENOVATION", "VEHICLE_PURCHASE"]
        )
        application_status = second.selectbox(
            "Trạng thái hồ sơ", ["SUBMITTED", "PENDING", "APPROVED"]
        )
        application_stage = first.selectbox(
            "Giai đoạn xử lý", ["UNDER_REVIEW", "DOCUMENT_CHECK", "DECISION"]
        )
        event_date = second.date_input("Ngày ghi nhận (UTC)", value=now.date())
        event_time = first.time_input("Giờ ghi nhận (UTC)", value=now.time())

        _section("2. Người nộp hồ sơ và khách hàng")
        first, second = st.columns(2)
        applicant_identifier = first.text_input("Mã người nộp hồ sơ", "APL-BANKA-0001")
        applicant_name = second.text_input("Tên người nộp hồ sơ", "Nguyen Van Demo")
        customer_identifier = first.text_input("Mã khách hàng", "CUST-41127322")
        customer_name = second.text_input("Tên khách hàng", "Nguyen Van Demo")
        customer_type = first.selectbox("Loại khách hàng", ["INDIVIDUAL", "BUSINESS"])
        address_country_code = second.text_input("Mã quốc gia", "VN", max_chars=3)

        _section("3. Định danh và liên hệ")
        first, second = st.columns(2)
        identification_number = first.text_input("CCCD / Số định danh", "079099009999")
        email = second.text_input("Email", "demo.application@example.com")
        phone = first.text_input("Số điện thoại", "0901234567")
        months_at_location = second.number_input(
            "Số tháng tại địa chỉ", min_value=0, value=24, step=1
        )

        _section("4. Nghề nghiệp và thu nhập")
        first, second = st.columns(2)
        employer_name = first.text_input("Đơn vị công tác", "Demo Company")
        employment_status = second.selectbox(
            "Trạng thái nghề nghiệp", ["EMPLOYED", "SELF_EMPLOYED", "UNEMPLOYED"]
        )
        monthly_income = first.number_input(
            "Thu nhập thường xuyên hàng tháng",
            min_value=0.0,
            value=25_000_000.0,
            step=1_000_000.0,
        )
        outstanding_debt = second.number_input(
            "Dư nợ hiện tại", min_value=0.0, value=5_000_000.0, step=1_000_000.0
        )

        _section("5. Kênh tiếp nhận")
        application_channel = st.selectbox(
            "Kênh tiếp nhận hồ sơ",
            channel_codes,
            index=channel_codes.index("MOBILE_APP"),
            format_func=lambda code: APPLICATION_CHANNELS[code]["label"],
        )
        st.caption(
            "application.channel và solution.channelType được ánh xạ đồng bộ theo quy ước của POC."
        )

        _section("6. Thiết bị")
        first, second = st.columns(2)
        device_identifier = first.text_input("Mã thiết bị", "DEV-APP-0001")
        ip_address = second.text_input("Địa chỉ IP", "203.0.113.42")

        _section("7. CIC")
        st.markdown(
            f'<div class="af-contract-note">Profile AF_CICIdentity được SAS quản lý. '
            f'Hai mảng profile giữ cùng capacity {AF_CIC_PROFILE_CAPACITY}; giao diện không sửa '
            "trực tiếp profile/count và chưa đưa các path CIC chưa xác minh vào request.</div>",
            unsafe_allow_html=True,
        )

        _section("8. Dữ liệu rủi ro Application Fraud")
        first, second = st.columns(2)
        bank_id = first.text_input("Mã đơn vị", "BANK-A")
        sales_agent_identifier = second.text_input(
            "Mã nhân viên/đại lý", "SALES-001"
        )
        disb_account_number = first.text_input(
            "Tài khoản nhận giải ngân", "09704000012345"
        )
        reference_phone = second.text_input("Điện thoại tham chiếu", "0912345678")
        normalized_address = st.text_input("Địa chỉ chuẩn hóa", "88 CONG HOA TP HCM")
        disb_owner_match = first.checkbox("Chủ tài khoản khớp người nộp", value=True)
        employer_unverified = second.checkbox("Đơn vị công tác chưa xác minh", value=False)
        st.caption("Các cửa sổ 7/30 ngày do SAS Profile và Variable Rule tính.")

        _section("9. Thông tin kỹ thuật")
        st.code(
            f"originationType={APPLICATION_ORIGINATION_TYPE} | "
            f"activityType={APPLICATION_ACTIVITY_TYPE} | "
            f"authenticationType={APPLICATION_AUTHENTICATION_TYPE} | "
            f"customerType={APPLICATION_CUSTOMER_TYPE}\n"
            f"transactionIdentifier={st.session_state['af_single_transaction_id']}",
            language="text",
        )
        submitted = st.form_submit_button(
            "Gửi hồ sơ", type="primary", use_container_width=True
        )

    values = {
        "message_datetime": _utc_string(event_date, event_time),
        "application_identifier": application_identifier,
        "transaction_identifier": st.session_state["af_single_transaction_id"],
        "application_type": application_type,
        "application_amount": application_amount,
        "currency_code": currency_code,
        "application_channel": application_channel,
        "application_purpose": application_purpose,
        "application_status": application_status,
        "application_stage": application_stage,
        "applicant_identifier": applicant_identifier,
        "applicant_name": applicant_name,
        "monthly_regular_income": monthly_income,
        "outstanding_debt": outstanding_debt,
        "employer_name": employer_name,
        "employment_status": employment_status,
        "customer_identifier": customer_identifier,
        "customer_name": customer_name,
        "customer_type": customer_type,
        "address_country_code": address_country_code.upper(),
        "identification_number": identification_number,
        "email": email,
        "phone": phone,
        "months_at_location": months_at_location,
        "device_identifier": device_identifier,
        "device_ip_address": ip_address,
        "app_risk": {
            "bankId": bank_id,
            "salesAgentIdentifier": sales_agent_identifier,
            "disbAcctNumber": disb_account_number,
            "referencePhone": reference_phone,
            "normalizedAddress": normalized_address,
            "disbAcctOwnerMatchInd": int(disb_owner_match),
            "employerUnverifiedInd": int(employer_unverified),
        },
    }
    try:
        payload = build_application_fraud_payload(values)
        validation_errors = validate_application_fraud_payload(payload)
    except ValueError as error:
        payload = None
        validation_errors = [str(error)]

    _section("Xem trước JSON")
    if payload is not None:
        st.json(payload, expanded=False)
    for error in validation_errors:
        st.error(error)

    if submitted:
        transaction_id = st.session_state["af_single_transaction_id"]
        if st.session_state["af_single_sending"] or (
            st.session_state["af_single_last_transaction"] == transaction_id
        ):
            st.warning("Request này đã được ghi nhận; ứng dụng không gửi lại khi rerun.")
        elif validation_errors or payload is None:
            st.error("Dữ liệu chưa hợp lệ; request chưa được gửi.")
        else:
            st.session_state["af_single_sending"] = True
            st.session_state["af_single_last_transaction"] = transaction_id
            try:
                with st.spinner("Đang chờ SAS Fraud Runtime..."):
                    response = send_message(
                        endpoint=endpoint,
                        payload=payload,
                        timeout_seconds=timeout_seconds,
                        verify_tls=verify_tls,
                        ca_bundle=ca_bundle,
                    )
                st.session_state["af_single_result"] = {
                    "payload": payload,
                    "response": response,
                }
                _record_alert_if_created(payload, response)
            except requests.exceptions.SSLError as error:
                st.session_state["af_single_last_transaction"] = None
                st.error(f"SSL error: {error}")
            except requests.exceptions.Timeout as error:
                st.session_state["af_single_last_transaction"] = None
                st.error(f"Timeout: {error}")
            except requests.exceptions.ConnectionError as error:
                st.session_state["af_single_last_transaction"] = None
                st.error(f"DNS/connection error: {error}")
            except (requests.RequestException, ValueError) as error:
                st.session_state["af_single_last_transaction"] = None
                st.error(f"Gửi thất bại: {error}")
            finally:
                st.session_state["af_single_sending"] = False

    result = st.session_state.get("af_single_result")
    if result:
        _render_single_result(result)


def _filtered_results(results: list[dict[str, Any]], selected: str) -> list[dict[str, Any]]:
    if selected == "Có cảnh báo":
        return [result for result in results if result.get("alertFlg")]
    if selected == "Không cảnh báo":
        return [
            result
            for result in results
            if result.get("requestStatus") == "Request thành công"
            and not result.get("alertFlg")
        ]
    if selected == "Rule đã fire":
        return [result for result in results if result.get("firedFlg")]
    if selected == "Gửi thất bại":
        return [result for result in results if result.get("requestStatus") == "Gửi thất bại"]
    if selected == "Payload không hợp lệ":
        return [
            result
            for result in results
            if result.get("requestStatus") == "Payload không hợp lệ"
        ]
    return results


def _render_batch_results(results: list[dict[str, Any]]) -> None:
    _section("Kết quả xử lý")
    success = sum(item.get("requestStatus") == "Request thành công" for item in results)
    failed = sum(item.get("requestStatus") == "Gửi thất bại" for item in results)
    alert = sum(bool(item.get("alertFlg")) for item in results)
    no_alert = sum(
        item.get("requestStatus") == "Request thành công" and not item.get("alertFlg")
        for item in results
    )
    columns = st.columns(4)
    columns[0].metric("Thành công", success)
    columns[1].metric("Thất bại", failed)
    columns[2].metric("Có cảnh báo", alert)
    columns[3].metric("Không cảnh báo", no_alert)

    selected_filter = st.selectbox(
        "Lọc kết quả",
        [
            "Tất cả",
            "Có cảnh báo",
            "Không cảnh báo",
            "Rule đã fire",
            "Gửi thất bại",
            "Payload không hợp lệ",
        ],
        key="af_batch_filter",
    )
    filtered = _filtered_results(results, selected_filter)
    st.dataframe(
        [{column: row.get(column) for column in RESULT_COLUMNS} for row in filtered],
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Tải kết quả CSV",
        data=results_to_csv(results),
        file_name="application_fraud_batch_results.csv",
        mime="text/csv",
        key="af_download_results",
        use_container_width=True,
    )
    if filtered:
        labels = [
            f"Dòng {item['rowNumber']} — {item['applicationIdentifier']}" for item in filtered
        ]
        selected_label = st.selectbox("Chi tiết từng dòng", labels, key="af_result_detail")
        detail = filtered[labels.index(selected_label)]
        with st.expander("Request JSON", expanded=False):
            if detail.get("_request") is None:
                st.info("Dòng không hợp lệ nên không tạo/gửi request.")
            else:
                st.json(detail["_request"], expanded=False)
        with st.expander("Chi tiết phản hồi", expanded=False):
            if detail.get("_parsedResponse") is not None:
                st.json(detail["_parsedResponse"], expanded=False)
            elif detail.get("_rawResponse"):
                st.code(detail["_rawResponse"], language="text", wrap_lines=True)
            else:
                st.info(detail.get("errorMessage") or "Không có phản hồi từ runtime.")


def _render_batch(
    *, endpoint: str, timeout_seconds: float, verify_tls: bool, ca_bundle: str | None
) -> None:
    st.download_button(
        "Tải CSV mẫu",
        data=application_csv_template(),
        file_name="application_fraud_template.csv",
        mime="text/csv",
        key="af_download_template",
        use_container_width=True,
    )
    uploaded = st.file_uploader(
        "Chọn tệp CSV", type=["csv"], key="af_csv_upload", accept_multiple_files=False
    )
    if uploaded is None:
        st.info("Tải CSV mẫu, điền dữ liệu và upload để kiểm tra trước khi gửi.")
        return

    data = uploaded.getvalue()
    fingerprint = hashlib.sha256(data).hexdigest()
    reset_batch_for_new_file(st.session_state, fingerprint)
    validation = st.session_state.get("af_batch_validation")
    if validation is None:
        validation = parse_application_csv(data)
        st.session_state["af_batch_validation"] = validation
        st.session_state["af_batch_validated_rows"] = validation.valid_rows
        st.session_state["af_batch_validation_errors"] = validation.errors

    _section("Kiểm tra dữ liệu")
    st.caption(
        f"{len(validation.rows)} dòng dữ liệu · {len(validation.valid_rows)} hợp lệ · "
        f"{len(validation.errors)} lỗi"
    )
    if validation.rows:
        preview_columns = [column for column in validation.columns if column]
        st.dataframe(
            [
                {column: row.get(column, "") for column in preview_columns}
                for row in validation.rows[:100]
            ],
            use_container_width=True,
            hide_index=True,
        )
    if validation.errors:
        st.dataframe(validation.errors, use_container_width=True, hide_index=True)
    else:
        st.success("Toàn bộ dữ liệu hợp lệ.")

    first, second, third = st.columns(3)
    delay_seconds = first.number_input(
        "Khoảng nghỉ giữa request (giây)",
        min_value=0.0,
        max_value=60.0,
        value=0.5,
        step=0.1,
        key="af_batch_delay",
    )
    batch_timeout = second.number_input(
        "Timeout mỗi request (giây)",
        min_value=1.0,
        max_value=300.0,
        value=float(timeout_seconds),
        step=1.0,
        key="af_batch_timeout",
    )
    stop_mode = third.selectbox(
        "Khi có lỗi", ["Tiếp tục", "Dừng batch"], key="af_batch_stop_mode"
    )
    confirmed = st.checkbox(
        "Tôi đã kiểm tra dữ liệu; chỉ gửi các dòng hợp lệ.", key="af_batch_confirm"
    )
    already_completed = (
        st.session_state.get("af_batch_completed_fingerprint") == fingerprint
    )
    run_clicked = st.button(
        "Chạy batch",
        type="primary",
        key="af_run_batch",
        disabled=(
            not validation.valid_rows
            or not confirmed
            or st.session_state.get("af_batch_running", False)
            or already_completed
        ),
        use_container_width=True,
    )
    if already_completed:
        st.caption(
            "Tệp này đã chạy trong session hiện tại. Upload tệp khác để tạo batch mới."
        )

    if run_clicked:
        if not claim_batch_run(st.session_state, fingerprint):
            st.warning("Batch đang chạy hoặc đã hoàn tất; không gửi lặp lại.")
        else:
            st.session_state["af_batch_status"] = "running"
            st.session_state["af_batch_progress"] = 0
            progress_bar = st.progress(0.0)
            current_text = st.empty()
            metric_columns = st.columns(4)
            counters = {"success": 0, "failed": 0, "alert": 0, "no_alert": 0}

            def update_progress(
                current: int,
                total: int,
                row: dict[str, str],
                result: dict[str, Any],
            ) -> None:
                progress_bar.progress(current / total)
                st.session_state["af_batch_progress"] = current
                current_text.write(
                    f"Dòng {current}/{total} · Hồ sơ {row.get('applicationIdentifier', '')}"
                )
                if result.get("requestStatus") == "Request thành công":
                    counters["success"] += 1
                    counters["alert" if result.get("alertFlg") else "no_alert"] += 1
                else:
                    counters["failed"] += 1
                metric_columns[0].metric("Thành công", counters["success"])
                metric_columns[1].metric("Thất bại", counters["failed"])
                metric_columns[2].metric("Có cảnh báo", counters["alert"])
                metric_columns[3].metric("Không cảnh báo", counters["no_alert"])

            try:
                sent_results = execute_application_batch(
                    validation.valid_rows,
                    endpoint=endpoint,
                    timeout_seconds=float(batch_timeout),
                    verify_tls=verify_tls,
                    ca_bundle=ca_bundle,
                    delay_seconds=float(delay_seconds),
                    stop_on_error=stop_mode == "Dừng batch",
                    progress=update_progress,
                )
                all_results = invalid_batch_results(validation) + sent_results
                st.session_state["af_batch_results"] = sorted(
                    all_results, key=lambda item: item["rowNumber"]
                )
                st.session_state["af_batch_details"] = {
                    int(item["rowNumber"]): {
                        "request": item.get("_request"),
                        "response": item.get("_parsedResponse"),
                        "rawResponse": item.get("_rawResponse"),
                    }
                    for item in all_results
                }
                st.session_state["af_batch_status"] = "completed"
            except Exception as error:  # UI boundary: never expose a stack trace.
                st.session_state["af_batch_status"] = "failed"
                st.error(f"Batch dừng do lỗi không mong đợi: {error}")
            finally:
                finish_batch_run(st.session_state, fingerprint)

    results = st.session_state.get("af_batch_results", [])
    if results:
        _render_batch_results(results)


def render_application_workspace(
    *, endpoint: str, timeout_seconds: float, verify_tls: bool, ca_bundle: str | None
) -> None:
    _initialize_state()
    _render_styles()
    st.markdown(
        """
        <div class="af-console-header">
          <h2>Application Fraud</h2>
          <p>Kiểm thử hồ sơ trên SAS Fraud Runtime</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    single_tab, batch_tab = st.tabs(["Nhập một hồ sơ", "Gửi hồ sơ từ CSV"])
    with single_tab:
        _render_single(
            endpoint=endpoint,
            timeout_seconds=timeout_seconds,
            verify_tls=verify_tls,
            ca_bundle=ca_bundle,
        )
    with batch_tab:
        _render_batch(
            endpoint=endpoint,
            timeout_seconds=timeout_seconds,
            verify_tls=verify_tls,
            ca_bundle=ca_bundle,
        )
