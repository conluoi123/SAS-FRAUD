"""End-to-end smoke test: every scenario must render without a Streamlit exception.

Uses Streamlit's own AppTest harness to drive the sidebar Family/Scenario
selectboxes exactly like a user would, then asserts the run raised nothing.
Unit tests in test_streamlit_console.py cover the pure-Python payload/checks
logic; this file catches Streamlit-specific issues those can't (duplicate
widget IDs, KeyErrors on a scenario's own extra fields, etc.).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

from app.streamlit_console.application_config import APPLICATION_CHANNELS  # noqa: E402
from app.streamlit_console.scenarios import SCENARIOS  # noqa: E402

APP_PATH = str(
    Path(__file__).resolve().parent.parent / "app" / "streamlit_console" / "app.py"
)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.key for s in SCENARIOS])
def test_scenario_renders_without_exception(scenario) -> None:
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)

    at.sidebar.radio[0].set_value("Payment Fraud").run(timeout=30)
    at.sidebar.selectbox[0].set_value(scenario.family).run(timeout=30)
    at.sidebar.selectbox[1].set_value(scenario.label).run(timeout=30)

    assert list(at.exception) == []


def test_application_workspace_renders_without_exception() -> None:
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)

    at.sidebar.radio[0].set_value("Application Fraud").run(timeout=30)

    assert list(at.exception) == []


def test_application_workspace_renders_all_six_channel_contexts() -> None:
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)

    for channel, config in APPLICATION_CHANNELS.items():
        channel_widget = next(
            widget for widget in at.selectbox if widget.label == "Kênh tiếp nhận"
        )
        channel_widget.set_value(channel).run(timeout=30)
        assert list(at.exception) == []
        assert any(
            config["business_description"] in str(message.value) for message in at.info
        )


def test_json_editor_apply_form_merge_and_restore_work_in_apptest() -> None:
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)

    edit_toggle = next(widget for widget in at.toggle if widget.label == "Edit JSON")
    edit_toggle.set_value(True).run(timeout=30)
    editor = next(widget for widget in at.text_area if widget.label == "Request JSON")
    payload = json.loads(editor.value)
    payload["message"]["qaOnlyExtension"] = {"preserve": True}
    editor.set_value(json.dumps(payload, ensure_ascii=False)).run(timeout=30)

    apply_button = next(
        button for button in at.button if button.label == "Validate & Apply"
    )
    apply_button.click().run(timeout=30)
    assert list(at.exception) == []
    assert at.session_state["af_effective_payload"]["message"]["qaOnlyExtension"] == {
        "preserve": True
    }

    applicant_name = next(
        widget for widget in at.text_input if widget.label == "Họ và tên người vay"
    )
    applicant_name.set_value("Nguyễn Văn QA").run(timeout=30)
    assert at.session_state["af_effective_payload"]["message"]["qaOnlyExtension"] == {
        "preserve": True
    }

    restore_button = next(
        button for button in at.button if button.label == "Restore / Rebuild from Form"
    )
    restore_button.click().run(timeout=30)
    assert list(at.exception) == []
    assert "qaOnlyExtension" not in at.session_state["af_effective_payload"]["message"]


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


APPLICATION_HISTORY_PAGE_PATH = str(
    Path(__file__).resolve().parent.parent
    / "app"
    / "streamlit_console"
    / "pages"
    / "2_Application_History.py"
)


def test_application_history_page_renders_without_exception() -> None:
    at = AppTest.from_file(APPLICATION_HISTORY_PAGE_PATH)
    at.run(timeout=30)

    assert list(at.exception) == []
