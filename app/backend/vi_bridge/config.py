"""Configuration for the Alert Triage -> Visual Investigator bridge.

All values come from environment variables (loaded from .env via
python-dotenv, same pattern already used elsewhere in this project). See
.env.example for the full list of variables this module expects.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ViConfig:
    base_url: str
    tls_verify: bool
    username: str
    password: str
    domain_id: str
    alert_origin_code: str
    request_timeout_seconds: int


def _get_bool(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() == "true"


def load_vi_config() -> ViConfig:
    """Load VI connection settings from the environment.

    Raises KeyError with a clear message if a required variable is missing,
    instead of silently defaulting to something that looks plausible but
    is wrong (matches the "verify, don't guess" approach used throughout
    this project's docs/visual-investigator-alert-integration-runbook.md).
    """
    missing = [
        name
        for name in ("VI_BASE_URL", "VI_USERNAME", "VI_PASSWORD")
        if not os.environ.get(name)
    ]
    if missing:
        raise KeyError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Copy .env.example to .env and fill these in first."
        )

    return ViConfig(
        base_url=os.environ["VI_BASE_URL"].rstrip("/"),
        tls_verify=_get_bool("VI_TLS_VERIFY", "false"),
        username=os.environ["VI_USERNAME"],
        password=os.environ["VI_PASSWORD"],
        domain_id=os.environ.get("VI_DOMAIN_ID", "svidomain"),
        alert_origin_code=os.environ.get("VI_ALERT_ORIGIN_CODE", "AT"),
        request_timeout_seconds=int(os.environ.get("VI_REQUEST_TIMEOUT_SECONDS", "30")),
    )
