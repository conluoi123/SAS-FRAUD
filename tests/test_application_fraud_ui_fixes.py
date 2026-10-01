import pytest
from unittest.mock import patch, MagicMock
from app.streamlit_console.sas_response import extract_application_fired_rules, normalize_application_result, ApplicationFiredRule
from app.streamlit_console.application_workspace import (
    application_business_fingerprint,
    apply_new_application_same_customer,
    apply_fresh_test_dataset,
    _record_alert_if_created,
    _render_single,
    _render_quick_demos,
)
from app.streamlit_console.sas_client import send_message
from app.streamlit_console.application_batch import execute_application_batch
from app.streamlit_console.application_demo import run_demo_steps


def test_text_plain_manual_call():
    # manual call uses send_message directly with as_text_plain=True
    with patch("app.streamlit_console.sas_client.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, text="{}")
        send_message(endpoint="http://test", payload={"message": {}}, timeout_seconds=10, verify_tls=False, ca_bundle=None, as_text_plain=True)
        mock_post.assert_called_once()
        kwargs = mock_post.call_args.kwargs
        assert kwargs["headers"]["Content-Type"] == "text/plain; charset=utf-8"


def test_text_plain_batch_call():
    with patch("app.streamlit_console.application_batch.send_message") as mock_send, \
         patch("app.streamlit_console.application_batch.validate_application_fraud_payload") as mock_val, \
         patch("app.streamlit_console.application_batch.map_application_csv_row") as mock_map:
        mock_map.return_value = {"message": {}}
        mock_val.return_value = []
        mock_send.return_value = MagicMock(status_code=200, parsed_body={})
        rows = [{"application_identifier": "1", "customer_identifier": "2", "_rowNumber": "2"}]
        execute_application_batch(rows, endpoint="http://test", timeout_seconds=10, verify_tls=False, ca_bundle=None, sender=mock_send)
        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs.get("as_text_plain") is True


def test_text_plain_quick_demo_call():
    with patch("app.streamlit_console.application_demo.send_message") as mock_send, \
         patch("app.streamlit_console.application_demo.validate_application_fraud_payload") as mock_val, \
         patch("app.streamlit_console.application_demo.build_application_fraud_payload") as mock_build:
        mock_val.return_value = []
        mock_build.return_value = {"message": {}}
        mock_send.return_value = MagicMock(status_code=200, parsed_body={})
        step = MagicMock()
        step.label = "test"
        step.values = {}
        run_demo_steps([step], endpoint="http://test", timeout_seconds=10, verify_tls=False, ca_bundle=None, sender=mock_send, delay_seconds=0)
        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs.get("as_text_plain") is True


def test_50083_3_response_shape():
    parsed = {
        "message": {
            "appRisk": {
                "firedRuleSummary": "AF_DR_Shared_Reference_Network",
                "firedRuleRefSummary": "50083.3",
                "alertReasonSummary": "Multiple customers are using the same reference phone and disbursement account."
            },
            "sas": {
                "rulefired": [
                    {
                        "ruleIdentifier": "ade62644-5c44-48ef-8df9-f8ed91131c65",
                        "referenceIdentifier": "50083.3",
                        "alertReason": "Multiple customers are using...",
                        "alertFlg": 1,
                        "firedFlg": 1
                    }
                ]
            }
        }
    }
    
    rules = extract_application_fired_rules(parsed)
    assert len(rules) == 1
    rule = rules[0]
    
    # appRisk firedRuleSummary takes precedence for display
    assert rule.display_name == "AF_DR_Shared_Reference_Network"
    
    # alertReason is not displayed as rule name, it is a separate field
    assert rule.reason == "Multiple customers are using the same reference phone and disbursement account."


def test_duplicate_rerun_blocked_and_allowed():
    payload1 = {
        "message": {
            "sas": {
                "system": {
                    "transactionIdentifier": "TX1"
                }
            },
            "application": {
                "identifier": "APP1"
            }
        }
    }
    
    fp1 = application_business_fingerprint(payload1)
    
    # changed Application ID allowed
    payload2 = {
        "message": {
            "sas": {
                "system": {
                    "transactionIdentifier": "TX1"
                }
            },
            "application": {
                "identifier": "APP2" # Changed
            }
        }
    }
    fp2 = application_business_fingerprint(payload2)
    
    assert fp1 != fp2, "Fingerprint should change when business data changes"
    
    # duplicate rerun blocked logic simulation
    state = {
        "af_single_last_fingerprint": fp1,
        "af_single_last_transaction": "TX1"
    }
    
    # Simulate same payload
    assert application_business_fingerprint(payload1) == state["af_single_last_fingerprint"]
    
    # Simulate changed payload
    assert application_business_fingerprint(payload2) != state["af_single_last_fingerprint"]
    
    # reset clears duplicate state
    apply_fresh_test_dataset(state)
    assert state["af_single_last_fingerprint"] is None
    
    # new application generates new transactionIdentifier
    apply_new_application_same_customer(state)
    assert state["af_single_last_fingerprint"] is None


def test_sticky_alert_dialog_lifecycle():
    mock_payload = {
        "message": {
            "application": {"identifier": "APP1"},
            "customer": {"identifier": "CUST1", "surname": "Test"}
        }
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.elapsed_ms = 100
    mock_response.parse_error = False
    mock_response.parsed_body = {
        "message": {
            "appRisk": {
                "firedRuleSummary": "Test",
                "alertReasonSummary": "Test"
            },
            "sas": {
                "rulefired": [
                    {"ruleIdentifier": "1", "alertFlg": 1, "firedFlg": 1}
                ]
            }
        }
    }

    state = {}
    mock_st = MagicMock()
    mock_st.session_state = state

    with patch("app.streamlit_console.application_workspace.st", mock_st):
        with patch("app.streamlit_console.application_workspace.record_alert"):
            # A. new manual alert -> popup event exists
            _record_alert_if_created(mock_payload, mock_response, show_dialog=True)

        assert "af_pending_result_dialog" in state
        assert state["af_pending_result_dialog"] is not None

        # B. event is consumed once
        with patch("app.streamlit_console.application_workspace._show_application_result_dialog") as mock_show:
            with patch("app.streamlit_console.application_workspace._section"):
                try:
                    _render_single(endpoint="", timeout_seconds=10, verify_tls=False, ca_bundle=None)
                except Exception:
                    pass
                mock_show.assert_called_once()
        
        # C. subsequent rerun -> no popup
        assert state.get("af_pending_result_dialog") is None

        # D. new second alert -> popup opens once again
        with patch("app.streamlit_console.application_workspace.record_alert"):
            _record_alert_if_created(mock_payload, mock_response, show_dialog=True)
        assert state["af_pending_result_dialog"] is not None
        with patch("app.streamlit_console.application_workspace._show_application_result_dialog") as mock_show:
            with patch("app.streamlit_console.application_workspace._section"):
                try:
                    _render_single(endpoint="", timeout_seconds=10, verify_tls=False, ca_bundle=None)
                except Exception:
                    pass
                mock_show.assert_called_once()
        assert state.get("af_pending_result_dialog") is None

        # E. Quick Demo follows same lifecycle
        state["af_demo_pending_dialog"] = {"test": "data"}
        with patch("app.streamlit_console.application_workspace._show_quick_demo_result_dialog") as mock_show_demo:
            try:
                _render_quick_demos(endpoint="", timeout_seconds=10, verify_tls=False, ca_bundle=None)
            except Exception:
                pass
            mock_show_demo.assert_called_once()
                    
        assert state.get("af_demo_pending_dialog") is None

        # F. no-alert response -> no popup
        mock_response.parsed_body["message"]["sas"]["rulefired"] = []
        with patch("app.streamlit_console.application_workspace.record_alert"):
            _record_alert_if_created(mock_payload, mock_response, show_dialog=True)
                
        assert state.get("af_pending_result_dialog") is None
        # G. old alert record remains stored (simulated by record_alert mock above which does nothing, but popup is not set)

