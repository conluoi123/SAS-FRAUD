"""Alert Triage -> SAS Visual Investigator integration bridge (Phần B: no Kafka yet).

This package currently covers everything that does NOT require a live Kafka
connection:
  - resolving or creating the "Known Object" in VI (svi-datahub API)
  - mapping an Alert Triage transaction type to a VI entity type
  - building the alertingEvent payload
  - posting it to the VI Alerts API (svi-alert)

The Kafka consumer itself (reading transaction-topic-mark) is intentionally
NOT implemented yet — network access to the Kafka broker is still blocked
(see docs/visual-investigator-alert-integration-runbook.md and the chat log
for the pending question to the SAS admin/mentor). Once that is resolved,
a `consumer.py` module can call `run_bridge_for_mark()` in
`run_manual_test.py` for each message it reads.
"""
