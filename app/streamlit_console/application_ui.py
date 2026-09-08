"""Application Fraud entry points used by the shared Streamlit console."""

from __future__ import annotations

from typing import Callable

try:
    from .application_scenarios import APPLICATION_SCENARIOS, ApplicationScenario
    from .application_workspace import render_application_workspace
    from .sas_client import SasRuntimeResponse
except ImportError:
    from application_scenarios import APPLICATION_SCENARIOS, ApplicationScenario
    from application_workspace import render_application_workspace
    from sas_client import SasRuntimeResponse


def select_application_scenario() -> ApplicationScenario:
    """Keep app integration stable without exposing synthetic rule scenarios."""

    return APPLICATION_SCENARIOS[0]


def render_application_console(
    scenario: ApplicationScenario,
    *,
    endpoint: str,
    timeout_seconds: float,
    verify_tls: bool,
    ca_bundle: str | None,
    render_response: Callable[[SasRuntimeResponse, str], None] | None = None,
) -> None:
    """Render the operational single/batch Application Fraud workspace."""

    del scenario, render_response
    render_application_workspace(
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        verify_tls=verify_tls,
        ca_bundle=ca_bundle,
    )
