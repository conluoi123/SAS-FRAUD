"""OAuth token retrieval for SAS Viya / Visual Investigator REST APIs.

Matches the flow already verified working in
docs/visual-investigator-alert-integration-runbook.md (section 7): a
password grant against /SASLogon/oauth/token using the "sas.cli" public
client. The token expires in ~3599 seconds (~1 hour) — callers should not
cache it beyond a single bridge run.
"""

from __future__ import annotations

import requests

from .config import ViConfig


def get_oauth_token(config: ViConfig) -> str:
    response = requests.post(
        f"{config.base_url}/SASLogon/oauth/token",
        auth=("sas.cli", ""),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "password",
            "username": config.username,
            "password": config.password,
        },
        verify=config.tls_verify,
        timeout=config.request_timeout_seconds,
    )
    response.raise_for_status()
    body = response.json()
    token = body.get("access_token")
    if not token:
        raise RuntimeError(f"SASLogon response had no access_token: {body}")
    return token
