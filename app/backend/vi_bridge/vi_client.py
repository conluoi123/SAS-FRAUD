"""HTTP calls to two SAS Visual Investigator REST APIs.

Endpoints below were confirmed against the official spec, not guessed:
  - svi-datahub: https://developer.sas.com/rest-apis/svi-datahub
    (operationIds: getFilteredDocumentCollection, createNewInternalDocument,
    per the openapi.yml for svi-datahub-v11)
  - svi-alert:   https://developer.sas.com/rest-apis/svi-alert
    (operationId: createAlertingEventsFromFlatAndNested), and already
    verified working end-to-end in
    docs/visual-investigator-alert-integration-runbook.md (HTTP 201).

Assumption not yet verified against a live call: svi-datahub is reachable
at {VI_BASE_URL}/svi-datahub/... following the same gateway path pattern
as svi-alert ({VI_BASE_URL}/svi-alert/...). Confirm this on the first real
run — if it 404s, ask the VI admin for the correct base path.
"""

from __future__ import annotations

from typing import Any

import requests

from .config import ViConfig

FILTER_CONTENT_TYPE = "application/vnd.sas.investigation.data.document.filter.request+json"
FILTER_ACCEPT = "application/vnd.sas.collection+json"
FILTER_ACCEPT_ITEM = "application/vnd.sas.investigation.data.enriched.document+json"

CREATE_CONTENT_TYPE = "application/vnd.sas.investigation.data.enriched.document+json"

ALERTING_EVENT_CONTENT_TYPE = "application/vnd.sas.investigation.triage.alerting.data.nested+json"
ALERTING_EVENT_ACCEPT = "application/vnd.sas.investigation.triage.alerting.event.nested+json"


def _headers(token: str, content_type: str | None = None, accept: str | None = None,
             accept_item: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if content_type:
        headers["Content-Type"] = content_type
    if accept:
        headers["Accept"] = accept
    if accept_item:
        headers["Accept-Item"] = accept_item
    return headers


def find_document_by_field(
    config: ViConfig,
    token: str,
    entity_type: str,
    field_name: str,
    field_value: str,
) -> dict[str, Any] | None:
    """Return the first document where field_name == field_value, or None.

    Uses the documented "eq(field, 'value')" filter syntax. String values
    must be single-quoted in the filter expression itself.
    """
    url = f"{config.base_url}/svi-datahub/documents/{entity_type}"
    body = {"filter": f"eq({field_name},'{field_value}')", "limit": 1}
    response = requests.post(
        url,
        json=body,
        headers=_headers(
            token,
            content_type=FILTER_CONTENT_TYPE,
            accept=FILTER_ACCEPT,
            accept_item=FILTER_ACCEPT_ITEM,
        ),
        verify=config.tls_verify,
        timeout=config.request_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    # The response may come back as a sasCollection ({"items": [...]})
    # or as a plain array, depending on the Accept header the server
    # decides to honor. Handle both defensively.
    items = payload.get("items") if isinstance(payload, dict) else payload
    if not items:
        return None
    return items[0]


def create_document(
    config: ViConfig,
    token: str,
    entity_type: str,
    field_values: dict[str, Any],
) -> dict[str, Any]:
    """Create a new internal document (Known Object) of entity_type."""
    url = f"{config.base_url}/svi-datahub/documents"
    body = {"objectTypeName": entity_type, "fieldValues": field_values}
    response = requests.post(
        url,
        json=body,
        headers=_headers(token, content_type=CREATE_CONTENT_TYPE),
        verify=config.tls_verify,
        timeout=config.request_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def resolve_or_create_known_object(
    config: ViConfig,
    token: str,
    entity_type: str,
    source_field: str,
    source_value: str,
    extra_fields_if_created: dict[str, Any] | None = None,
) -> str:
    """Return the VI internal document id for source_value, creating it if needed.

    This is the function that answers "does a Known Object already exist
    for this Alert Triage account, or do we need to make one" (see the
    "known object" explanation earlier in the chat / runbook section 3.1).
    """
    existing = find_document_by_field(config, token, entity_type, source_field, source_value)
    if existing is not None:
        return existing["id"]

    field_values = {source_field: source_value, **(extra_fields_if_created or {})}
    created = create_document(config, token, entity_type, field_values)
    return created["id"]


def post_alerting_event(config: ViConfig, token: str, alerting_event_payload: dict[str, Any]) -> dict[str, Any]:
    """POST one alerting event (nested layout) to the VI Alerts API.

    Note: the official spec documents only 200 as a success response, but
    the real test environment returns 201 (see runbook section 8) — both
    are treated as success here.
    """
    url = f"{config.base_url}/svi-alert/alertingEvents"
    response = requests.post(
        url,
        json=alerting_event_payload,
        headers=_headers(
            token,
            content_type=ALERTING_EVENT_CONTENT_TYPE,
            accept=ALERTING_EVENT_ACCEPT,
        ),
        verify=config.tls_verify,
        timeout=config.request_timeout_seconds,
    )
    if response.status_code not in (200, 201):
        response.raise_for_status()
    return {"status_code": response.status_code, "body": _safe_json(response)}


def _safe_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text
