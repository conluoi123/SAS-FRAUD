from __future__ import annotations

from app.streamlit_console import application_history
from app.streamlit_console.sas_client import SasRuntimeResponse


def _payload(application_id: str, transaction_id: str) -> dict:
    return {
        "message": {
            "application": {
                "identifier": application_id,
                "type": "PERSONAL_LOAN",
                "amount": 50_000_000,
                "currencyCode": "VND",
                "channel": "MOBILE_APP",
            },
            "applicant": {
                "identifier": f"APL-{application_id}",
                "name": "Nguyen Van Demo",
            },
            "customer": {
                "identifier": f"CUST-{application_id}",
                "surname": "Nguyen Van Demo",
            },
            "sas": {"system": {"transactionIdentifier": transaction_id}},
        }
    }


def _response(*, alert: bool, entity: str | None = None) -> SasRuntimeResponse:
    rule = {
        "ruleName": "AF_DR_TEST",
        "alertReason": "Shared network" if alert else None,
        "firedFlg": alert,
        "alertFlg": alert,
    }
    alerted = (
        [{"outcomeEntity": entity, "outcomeEntityType": "app_fraud_app"}]
        if entity
        else []
    )
    parsed = {
        "message": {
            "sas": {
                "system": {"returnType": 0, "messageIdentifier": "MESSAGE-1"},
                "decision": {"outcomeName": "Review" if alert else "Continue"},
                "rulefired": [rule],
                "alerted": alerted,
            }
        }
    }
    return SasRuntimeResponse(200, 11, {}, "{}", parsed, None)


def _history_file(tmp_path, monkeypatch):
    path = tmp_path / ".application_history.json"
    monkeypatch.setattr(application_history, "HISTORY_FILE", path)
    return path


def test_normal_application_is_persisted(tmp_path, monkeypatch) -> None:
    _history_file(tmp_path, monkeypatch)
    payload = _payload("APP-NORMAL", "TXN-NORMAL")

    recorded = application_history.record_application_response(
        payload,
        _response(alert=False),
        source="single",
        processed_at="2026-09-16T08:00:00Z",
    )

    assert recorded is True
    entry = application_history.load_application_history()[0]
    assert entry["application_id"] == "APP-NORMAL"
    assert entry["request_status"] == "Request successful"
    assert entry["alert_created"] is False
    assert entry["transaction_id"] == "TXN-NORMAL"


def test_alert_application_and_entity_are_persisted(tmp_path, monkeypatch) -> None:
    _history_file(tmp_path, monkeypatch)
    payload = _payload("APP-ALERT", "TXN-ALERT")

    application_history.record_application_response(
        payload,
        _response(alert=True, entity="APP-ALERTED-ENTITY"),
        source="single",
    )

    entry = application_history.load_application_history()[0]
    assert entry["alert_created"] is True
    assert entry["alert_reason"] == "Shared network"
    assert entry["primary_alerted_entity"] == "APP-ALERTED-ENTITY"
    assert entry["primary_alerted_entity_type"] == "app_fraud_app"


def test_transaction_deduplication_blocks_streamlit_rerun(
    tmp_path, monkeypatch
) -> None:
    _history_file(tmp_path, monkeypatch)
    payload = _payload("APP-ONE", "TXN-STABLE")
    response = _response(alert=False)

    first = application_history.record_application_response(
        payload, response, source="single"
    )
    second = application_history.record_application_response(
        payload, response, source="single"
    )

    assert first is True
    assert second is False
    assert len(application_history.load_application_history()) == 1


def test_guided_demo_excludes_seeds_and_includes_only_final(
    tmp_path, monkeypatch
) -> None:
    _history_file(tmp_path, monkeypatch)
    seed = {
        "payload": _payload("APP-SEED", "TXN-SEED"),
        "response": _response(alert=False),
    }
    final = {
        "payload": _payload("APP-FINAL", "TXN-FINAL"),
        "response": _response(alert=True, entity="APP-FINAL"),
    }

    assert (
        application_history.record_guided_demo_history([seed], expected_step_count=2)
        is False
    )
    assert application_history.load_application_history() == []

    assert (
        application_history.record_guided_demo_history(
            [seed, final], expected_step_count=2
        )
        is True
    )
    history = application_history.load_application_history()
    assert [item["application_id"] for item in history] == ["APP-FINAL"]
    assert history[0]["source"] == "guided_demo"


def test_batch_records_submitted_rows_and_excludes_invalid_unsent_rows(
    tmp_path, monkeypatch
) -> None:
    _history_file(tmp_path, monkeypatch)
    success_payload = _payload("APP-BATCH-OK", "TXN-BATCH-OK")
    failed_payload = _payload("APP-BATCH-FAIL", "TXN-BATCH-FAIL")
    invalid_payload = _payload("APP-BATCH-INVALID", "TXN-BATCH-INVALID")
    results = [
        {
            "requestStatus": "Request successful",
            "httpStatus": 200,
            "processingTimeMs": 10,
            "_request": success_payload,
            "_parsedResponse": _response(alert=False).parsed_body,
            "_rawResponse": "{}",
            "errorType": "",
            "errorMessage": "",
        },
        {
            "requestStatus": "Submission failed",
            "httpStatus": None,
            "processingTimeMs": None,
            "_request": failed_payload,
            "_parsedResponse": None,
            "_rawResponse": "",
            "errorType": "Timeout",
            "errorMessage": "runtime timed out",
        },
        {
            "requestStatus": "Invalid payload",
            "_request": invalid_payload,
            "errorType": "Payload mapping error",
        },
    ]

    recorded = application_history.record_batch_history(
        results, processed_at_factory=lambda: "2026-09-16T08:00:00Z"
    )

    assert recorded == 2
    history = application_history.load_application_history()
    assert {item["application_id"] for item in history} == {
        "APP-BATCH-OK",
        "APP-BATCH-FAIL",
    }
    assert all(item["application_id"] != "APP-BATCH-INVALID" for item in history)


def test_alert_with_empty_alerted_entity_is_supported(tmp_path, monkeypatch) -> None:
    _history_file(tmp_path, monkeypatch)

    application_history.record_application_response(
        _payload("APP-NO-ENTITY", "TXN-NO-ENTITY"),
        _response(alert=True, entity=None),
        source="single",
    )

    entry = application_history.load_application_history()[0]
    assert entry["alert_created"] is True
    assert entry["alerted_entities"] == []
    assert entry["primary_alerted_entity"] is None
    assert entry["primary_alerted_entity_type"] is None
