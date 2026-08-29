"""Build a VI alertingEvent payload from a transaction-topic-mark message.

Field shape matches the payload that was manually verified end-to-end
(HTTP 201) in cnp-vi-alerting-event.json /
docs/visual-investigator-alert-integration-runbook.md.

KNOWN GAP (see chat discussion): the real transaction-topic-mark message
does NOT carry rich fields like transactionAmount, merchantName,
authenticationDecision, etc. Only what is listed under `enrichment` below
is actually available today. If analysts need the richer fields, a later
version of this bridge must fetch them from the Alert Triage transaction
table (e.g. the `alerts_transaction.DCCA` table seen in pgAdmin) by
markProperties.transactionId before calling build_alerting_event.
"""

from __future__ import annotations

from typing import Any

from .config import ViConfig
from .mapping import EntityTypeMapping


def build_alerting_event(
    mark_message: dict[str, Any],
    vi_object_id: str,
    entity_mapping: EntityTypeMapping,
    config: ViConfig,
) -> dict[str, Any]:
    mark_props = mark_message["markProperties"]

    alerting_event = {
        # markProperties.id is already a unique GUID per mark -> reuse it
        # directly as the idempotency key. Do NOT use generateIds / a
        # fresh random GUID here, or a re-delivered Kafka message would
        # create a duplicate alert.
        "alertingEventId": mark_props["id"],
        "actionableEntityType": entity_mapping.vi_entity_type,
        "actionableEntityId": vi_object_id,
        "alertOriginCode": config.alert_origin_code,
        "alertTypeCode": entity_mapping.vi_alert_type_code,
        "domainId": config.domain_id,
        "alertTriggerText": mark_props.get("transactionMarkLabel", ""),
        "scenarioFiredEvents": [
            {
                "scenarioFiredEventId": mark_props["id"],
                "scenarioId": mark_props["markConfigId"],
                "scenarioName": mark_props.get("transactionMarkLabel", mark_props["markConfigId"]),
                "scenarioOriginCode": config.alert_origin_code,
                "displayFlag": True,
                "displayTypeCode": "TEXT",
                "ruleId": mark_props["markConfigId"],
            }
        ],
        "enrichment": {
            "sourceAlertId": mark_props.get("alertId"),
            "sourceTransactionId": mark_props.get("transactionId"),
            "markConfigId": mark_props.get("markConfigId"),
            "reasonCodeId": mark_props.get("reasonCodeId"),
            "reasonCodeLabel": mark_props.get("reasonCodeLabel"),
            "memoText": mark_props.get("memoText"),
        },
    }

    return {"jsonLayout": "nested", "alertingEvents": [alerting_event]}
