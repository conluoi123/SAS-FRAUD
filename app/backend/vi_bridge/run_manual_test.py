"""Manual end-to-end test of the bridge logic — no Kafka required.

Uses the real transaction-topic-mark message captured earlier (saved in
sample_data/) to stand in for "a message just read from Kafka". Everything
downstream of that (resolve/create Known Object, build payload, POST to
VI) is exercised against the real, live VI environment.

Usage:
    cd "SAS-FRAUD"
    python -m app.backend.vi_bridge.run_manual_test

Requires .env to have VI_BASE_URL, VI_USERNAME, VI_PASSWORD set (copy from
.env.example).
"""

from __future__ import annotations

import json
from pathlib import Path

from . import vi_client
from .auth import get_oauth_token
from .builder import build_alerting_event
from .config import load_vi_config
from .mapping import resolve_entity_mapping, should_escalate

SAMPLE_MESSAGE_PATH = Path(__file__).parent / "sample_data" / "transaction_topic_mark_sample.json"


def run_bridge_for_mark(mark_message: dict) -> dict:
    """Run the full Phần B pipeline for one mark message. Returns the VI response."""
    config = load_vi_config()
    token = get_oauth_token(config)

    mark_props = mark_message["markProperties"]

    if not should_escalate(mark_props["rootMarkName"]):
        return {"skipped": True, "reason": f"rootMarkName={mark_props['rootMarkName']} does not need investigation"}

    entity_mapping = resolve_entity_mapping(mark_props["transactionTypeId"])
    source_value = mark_message["alertData"]["actionableEntityID"]

    vi_object_id = vi_client.resolve_or_create_known_object(
        config,
        token,
        entity_type=entity_mapping.vi_entity_type,
        source_field=entity_mapping.vi_source_field,
        source_value=source_value,
        extra_fields_if_created={"source_system": "Alert Triage"},
    )

    payload = build_alerting_event(mark_message, vi_object_id, entity_mapping, config)
    print("--- Payload about to be sent to VI ---")
    print(json.dumps(payload, indent=2))

    result = vi_client.post_alerting_event(config, token, payload)
    return result


if __name__ == "__main__":
    with open(SAMPLE_MESSAGE_PATH, encoding="utf-8") as f:
        sample_message = json.load(f)

    outcome = run_bridge_for_mark(sample_message)
    print("--- Result ---")
    print(json.dumps(outcome, indent=2, default=str))
