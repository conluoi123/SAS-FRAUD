"""Business-readable presentation of existing Application Fraud validation."""

from __future__ import annotations


FIELD_LABELS = {
    "application.identifier": "Application ID",
    "application.type": "Sản phẩm vay",
    "application.amount": "Số tiền đề nghị",
    "application.currencyCode": "Loại tiền",
    "application.channel": "Kênh tiếp nhận",
    "customer.identifier": "Customer ID",
    "applicant.identifier": "Applicant ID",
    "applicant.monthlyRegularIncome": "Thu nhập hàng tháng",
    "applicant.outstandingDebt": "Dư nợ hiện tại",
    "sas.system.transactionIdentifier": "Transaction ID",
    "request.messageDtTm": "Thời điểm gửi",
    "sas.system.messageDtTmUtc": "Thời điểm hệ thống",
}


def humanize_validation_error(error: str) -> str:
    """Translate known contract errors without adding new policy rules."""

    text = str(error)
    if text == "Application ID and transaction ID must be different.":
        return "Application ID và Transaction ID phải là hai giá trị khác nhau."
    if text.startswith("application.channel must be one of:"):
        allowed = text.split(":", 1)[1].strip().rstrip(".")
        return f"Kênh tiếp nhận không được hỗ trợ. Giá trị hợp lệ: {allowed}."
    if "application.channel and solution.channelType" in text:
        return "Kênh tiếp nhận và mã kênh kỹ thuật trong JSON không khớp nhau."

    for path, label in FIELD_LABELS.items():
        if text == f"{path} is required.":
            return f"{label} là trường bắt buộc."
        if text == f"{path} must be numeric.":
            return f"{label} phải là một giá trị số hợp lệ."
        if text == f"{path} must not be negative.":
            return f"{label} không được là số âm."
        if text == f"{path} must be a valid timestamp.":
            return f"{label} phải là thời gian ISO-8601 hợp lệ."
    return text


def humanize_validation_errors(errors: list[str]) -> list[str]:
    return [humanize_validation_error(error) for error in errors]
