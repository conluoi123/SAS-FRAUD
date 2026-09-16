"""Application Fraud contract values owned by this POC.

The channel codes below are project conventions, not an official SAS catalog.
Keeping them here prevents the UI, CSV mapper, and payload builder from drifting.
"""

from __future__ import annotations

from typing import Final


APPLICATION_CHANNELS: Final[dict[str, dict[str, str]]] = {
    "MOBILE_APP": {
        "label": "Ứng dụng di động",
        "solution_channel_type": "MA",
        "business_description": "Hồ sơ được khách hàng khởi tạo trên ứng dụng di động.",
        "source_identifier_label": "Sales Agent ID (thông tin nguồn tiếp nhận)",
    },
    "WEB": {
        "label": "Website / Online Lending",
        "solution_channel_type": "WB",
        "business_description": "Yêu cầu vay được khởi tạo trên website / online lending.",
        "source_identifier_label": "Sales Agent ID (thông tin nguồn tiếp nhận)",
    },
    "BRANCH": {
        "label": "Tại quầy / Chi nhánh",
        "solution_channel_type": "BR",
        "business_description": "Hồ sơ được nhân viên giao dịch tại quầy hoặc chi nhánh nhập.",
        "source_identifier_label": "Mã nhân viên nhập hồ sơ (Sales Agent ID)",
    },
    "SALES_AGENT": {
        "label": "Nhân viên kinh doanh",
        "solution_channel_type": "SA",
        "business_description": "Hồ sơ được tiếp nhận trực tiếp qua nhân viên kinh doanh.",
        "source_identifier_label": "Sales Agent ID",
    },
    "PARTNER": {
        "label": "Đối tác / Điểm bán",
        "solution_channel_type": "PT",
        "business_description": "Hồ sơ có nguồn từ đối tác hoặc điểm bán (Point of Sale).",
        "source_identifier_label": "Mã đối tác / điểm bán (Sales Agent ID)",
    },
    "CALL_CENTER": {
        "label": "Tổng đài",
        "solution_channel_type": "CC",
        "business_description": "Hồ sơ được hỗ trợ khởi tạo từ xa qua tổng đài.",
        "source_identifier_label": "Mã nhân viên hỗ trợ (Sales Agent ID)",
    },
}

APPLICATION_ORIGINATION_TYPE: Final = "AP"
APPLICATION_ACTIVITY_TYPE: Final = "SB"
APPLICATION_AUTHENTICATION_TYPE: Final = "NA"
APPLICATION_CUSTOMER_TYPE: Final = "IN"

# AF_CICIdentity profiles in the current POC expose two parallel arrays of ten
# elements. The console deliberately never edits or populates those arrays.
AF_CIC_PROFILE_CAPACITY: Final = 10


def application_channel_type(application_channel: str) -> str:
    """Return the POC channel code and reject values outside the catalog."""

    channel = str(application_channel or "").strip().upper()
    try:
        return APPLICATION_CHANNELS[channel]["solution_channel_type"]
    except KeyError as error:
        allowed = ", ".join(APPLICATION_CHANNELS)
        raise ValueError(f"application.channel must be one of: {allowed}.") from error
