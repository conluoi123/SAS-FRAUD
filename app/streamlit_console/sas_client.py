"""HTTP client for the SAS Detection runtime."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

try:
    from .sas_response import parse_sas_response
except ImportError:
    from sas_response import parse_sas_response


@dataclass(frozen=True)
class SasRuntimeResponse:
    status_code: int
    elapsed_ms: int
    headers: dict[str, str]
    raw_body: str
    parsed_body: Any
    parse_error: str | None


def _resolve_verify(verify_tls: bool, ca_bundle: str | None) -> bool | str:
    verify: bool | str = verify_tls
    if verify_tls and ca_bundle:
        certificate_path = Path(ca_bundle).expanduser()
        if not certificate_path.is_file():
            raise ValueError(f"CA bundle does not exist: {certificate_path}")
        verify = str(certificate_path)
    return verify


def send_message(
    *,
    endpoint: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    verify_tls: bool,
    ca_bundle: str | None = None,
) -> SasRuntimeResponse:
    """Send one message to the Detection runtime and preserve the raw response."""

    verify = _resolve_verify(verify_tls, ca_bundle)

    started = time.perf_counter()
    response = requests.post(
        endpoint,
        json=payload,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=timeout_seconds,
        verify=verify,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000)

    parsed_body: Any = None
    parse_error: str | None = None
    try:
        parsed_body = parse_sas_response(response.text)
    except ValueError as error:
        parse_error = str(error)

    return SasRuntimeResponse(
        status_code=response.status_code,
        elapsed_ms=elapsed_ms,
        headers={key: value for key, value in response.headers.items()},
        raw_body=response.text,
        parsed_body=parsed_body,
        parse_error=parse_error,
    )


def fetch_runtime_description(
    *,
    endpoint: str,
    timeout_seconds: float,
    verify_tls: bool,
    ca_bundle: str | None = None,
) -> dict[str, Any] | None:
    """GET the SAS decision/description endpoint. Returns parsed JSON, or None.

    Best-effort runtime status probe only: never raises, so a slow/unreachable
    description endpoint can never break Execute.
    """

    try:
        verify = _resolve_verify(verify_tls, ca_bundle)
    except ValueError:
        return None
    try:
        response = requests.get(
            endpoint,
            headers={"Accept": "application/json"},
            timeout=timeout_seconds,
            verify=verify,
        )
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    try:
        parsed = response.json()
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None
