"""End-to-end smoke test: every scenario must render without a Streamlit exception.

Uses Streamlit's own AppTest harness to drive the sidebar Family/Scenario
selectboxes exactly like a user would, then asserts the run raised nothing.
Unit tests in test_streamlit_console.py cover the pure-Python payload/checks
logic; this file catches Streamlit-specific issues those can't (duplicate
widget IDs, KeyErrors on a scenario's own extra fields, etc.).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

from app.streamlit_console.application_scenarios import (  # noqa: E402
    APPLICATION_SCENARIOS,
)
from app.streamlit_console.scenarios import SCENARIOS  # noqa: E402

APP_PATH = str(
    Path(__file__).resolve().parent.parent / "app" / "streamlit_console" / "app.py"
)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.key for s in SCENARIOS])
def test_scenario_renders_without_exception(scenario) -> None:
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)

    at.sidebar.selectbox[0].set_value(scenario.family).run(timeout=30)
    at.sidebar.selectbox[1].set_value(scenario.label).run(timeout=30)

    assert list(at.exception) == []


@pytest.mark.parametrize(
    "scenario",
    APPLICATION_SCENARIOS,
    ids=[scenario.key for scenario in APPLICATION_SCENARIOS],
)
def test_application_scenario_renders_without_exception(scenario) -> None:
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)

    at.sidebar.radio[0].set_value("Application Fraud").run(timeout=30)
    at.sidebar.selectbox[0].set_value(scenario.label).run(timeout=30)

    assert list(at.exception) == []


ALERT_LOG_PAGE_PATH = str(
    Path(__file__).resolve().parent.parent
    / "app"
    / "streamlit_console"
    / "pages"
    / "1_Alert_Log.py"
)


def test_alert_log_page_renders_without_exception() -> None:
    at = AppTest.from_file(ALERT_LOG_PAGE_PATH)
    at.run(timeout=30)

    assert list(at.exception) == []
