"""Lookup table: Alert Triage transactionTypeId -> VI entity type.

This is the ONE place that decides which VI entity type/page an incoming
mark belongs to. Add a new row only after a VI administrator has created
the matching entity type + Page Builder pages (see SAS Visual Investigator
Administrator's Guide, Chapter 7 and Chapter 17) — this module never
creates entity *types*, only entity *instances* (documents) of a type that
already exists in VI.

Today there is exactly one confirmed mapping: the CNP debit case that was
manually tested end-to-end (see
docs/visual-investigator-alert-integration-runbook.md, section 2).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntityTypeMapping:
    vi_entity_type: str  # objectTypeName / actionableEntityType in VI
    vi_source_field: str  # VI field that stores the Alert Triage business key
    vi_alert_type_code: str  # must already exist in VI's AlertTypes reference data


# Keyed by markProperties.transactionTypeId, as seen on the real
# transaction-topic-mark message.
TRANSACTION_TYPE_TO_ENTITY: dict[str, EntityTypeMapping] = {
    "DCCA": EntityTypeMapping(
        vi_entity_type="CNP_Debit_Account_Quoc",
        vi_source_field="source_account_id",
        vi_alert_type_code="CNP",
    ),
}

# Mark types that represent "this needs investigation". Marks not in this
# set (e.g. Confirmed Genuine / Suspected Genuine) are ignored by the
# bridge — see transactionMarkConfig.json for the full list of mark IDs.
ESCALATE_ROOT_MARKS = {"confirm_invalid", "marked_for_review"}


def resolve_entity_mapping(transaction_type_id: str) -> EntityTypeMapping:
    try:
        return TRANSACTION_TYPE_TO_ENTITY[transaction_type_id]
    except KeyError as exc:
        raise ValueError(
            f"No VI entity type mapping configured for transactionTypeId="
            f"{transaction_type_id!r}. Ask a VI administrator whether a new "
            "entity type + page needs to be created before adding a row "
            "to TRANSACTION_TYPE_TO_ENTITY."
        ) from exc


def should_escalate(root_mark_name: str) -> bool:
    return root_mark_name in ESCALATE_ROOT_MARKS
