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
    },
    "WEB": {
        "label": "Website / Online Lending",
        "solution_channel_type": "WB",
    },
    "BRANCH": {
        "label": "Chi nhánh / Phòng giao dịch",
        "solution_channel_type": "BR",
    },
    "SALES_AGENT": {
        "label": "Nhân viên / Đại lý bán hàng",
        "solution_channel_type": "SA",
    },
    "PARTNER": {
        "label": "Đối tác / Đại lý / Điểm bán",
        "solution_channel_type": "PT",
    },
    "CALL_CENTER": {
        "label": "Tổng đài",
        "solution_channel_type": "CC",
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
        raise ValueError(
            f"application.channel must be one of: {allowed}."
        ) from error
