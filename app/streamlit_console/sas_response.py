"""Parsing and summarizing SAS Detection runtime responses."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


class SasResponseParseError(ValueError):
    """Raised when a SAS text response cannot be converted to structured data."""


class _SasNotationParser:
    """Parse the object notation returned by the Detection runtime.

    The runtime can return a JSON string whose contents look like JSON but use
    unquoted object keys and bare timestamp values. This parser handles that
    representation without modifying the original response body.
    """

    def __init__(self, source: str) -> None:
        self.source = source
        self.position = 0

    def parse(self) -> Any:
        value = self._parse_value()
        self._skip_whitespace()
        if self.position != len(self.source):
            raise self._error("Unexpected trailing content")
        return value

    def _parse_value(self) -> Any:
        self._skip_whitespace()
        if self.position >= len(self.source):
            raise self._error("Expected a value")

        current = self.source[self.position]
        if current == "{":
            return self._parse_object()
        if current == "[":
            return self._parse_array()
        if current == '"':
            return self._parse_string()
        return self._parse_bare_value()

    def _parse_object(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        self.position += 1
        self._skip_whitespace()
        if self._consume("}"):
            return result

        while True:
            key = self._parse_key()
            self._skip_whitespace()
            if not self._consume(":"):
                raise self._error("Expected ':' after object key")
            result[key] = self._parse_value()
            self._skip_whitespace()
            if self._consume("}"):
                return result
            if not self._consume(","):
                raise self._error("Expected ',' or '}' in object")

    def _parse_array(self) -> list[Any]:
        result: list[Any] = []
        self.position += 1
        self._skip_whitespace()
        if self._consume("]"):
            return result

        while True:
            result.append(self._parse_value())
            self._skip_whitespace()
            if self._consume("]"):
                return result
            if not self._consume(","):
                raise self._error("Expected ',' or ']' in array")

    def _parse_key(self) -> str:
        self._skip_whitespace()
        if self.position < len(self.source) and self.source[self.position] == '"':
            return self._parse_string()

        start = self.position
        while self.position < len(self.source):
            if self.source[self.position] == ":":
                break
            if self.source[self.position] in "{},[]":
                raise self._error("Invalid unquoted object key")
            self.position += 1
        key = self.source[start : self.position].strip()
        if not key:
            raise self._error("Object key cannot be empty")
        return key

    def _parse_string(self) -> str:
        start = self.position
        self.position += 1
        escaped = False
        while self.position < len(self.source):
            current = self.source[self.position]
            self.position += 1
            if escaped:
                escaped = False
            elif current == "\\":
                escaped = True
            elif current == '"':
                return json.loads(self.source[start : self.position])
        raise self._error("Unterminated string")

    def _parse_bare_value(self) -> Any:
        start = self.position
        while self.position < len(self.source):
            if self.source[self.position] in ",]}":
                break
            self.position += 1

        token = self.source[start : self.position].strip()
        if not token:
            raise self._error("Bare value cannot be empty")
        if token in {"null", "<nil>"}:
            return None
        if token == "true":
            return True
        if token == "false":
            return False
        if re.fullmatch(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?", token):
            return float(token) if any(char in token for char in ".eE") else int(token)
        return token

    def _skip_whitespace(self) -> None:
        while self.position < len(self.source) and self.source[self.position].isspace():
            self.position += 1

    def _consume(self, expected: str) -> bool:
        if self.position < len(self.source) and self.source[self.position] == expected:
            self.position += 1
            return True
        return False

    def _error(self, message: str) -> SasResponseParseError:
        context = self.source[max(0, self.position - 25) : self.position + 25]
        return SasResponseParseError(f"{message} at {self.position}: {context!r}")


def parse_sas_response(raw_body: str) -> Any:
    """Convert JSON or SAS object notation to Python structures."""

    source = raw_body.strip()
    if not source:
        return None

    try:
        decoded = json.loads(source)
    except json.JSONDecodeError:
        decoded = source

    if not isinstance(decoded, str):
        return decoded

    decoded = decoded.strip()
    try:
        return json.loads(decoded)
    except json.JSONDecodeError:
        return _SasNotationParser(decoded).parse()


@dataclass(frozen=True)
class SasDecisionSummary:
    message_identifier: str | None
    transaction_identifier: str | None
    outcome: Any
    outcome_name: str | None
    reference_identifier: str | None
    alert_created: bool
    alerted_entities: list[dict[str, Any]]
    fired_rules: list[dict[str, Any]]
    evaluated_rule_count: int
    timings: dict[str, Any]


def summarize_sas_response(parsed: Any) -> SasDecisionSummary:
    """Extract fields used by the test console from a parsed response."""

    root = parsed if isinstance(parsed, dict) else {}
    message = root.get("message", {})
    sas = message.get("sas", {}) if isinstance(message, dict) else {}
    system = sas.get("system", {}) if isinstance(sas, dict) else {}
    decision = sas.get("decision", {}) if isinstance(sas, dict) else {}
    rules = sas.get("rulefired", []) if isinstance(sas, dict) else []
    alerted = sas.get("alerted", []) if isinstance(sas, dict) else []
    timings = sas.get("timings", {}) if isinstance(sas, dict) else {}

    rules = (
        rules
        if isinstance(rules, list)
        else ([rules] if isinstance(rules, dict) else [])
    )
    alerted_signal = bool(alerted)
    alerted = (
        alerted
        if isinstance(alerted, list)
        else ([alerted] if isinstance(alerted, dict) else [])
    )

    def flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y"}
        return bool(value)

    fired_rules = [
        rule
        for rule in rules
        if isinstance(rule, dict)
        and (flag(rule.get("firedFlg")) or flag(rule.get("alertFlg")))
    ]

    return SasDecisionSummary(
        message_identifier=system.get("messageIdentifier"),
        transaction_identifier=system.get("transactionIdentifier"),
        outcome=decision.get("outcome"),
        outcome_name=decision.get("outcomeName"),
        reference_identifier=decision.get("referenceIdentifier"),
        alert_created=alerted_signal
        or any(flag(rule.get("alertFlg")) for rule in fired_rules),
        alerted_entities=[item for item in alerted if isinstance(item, dict)],
        fired_rules=fired_rules,
        evaluated_rule_count=len(rules),
        timings=timings if isinstance(timings, dict) else {},
    )


_IDENTIFIER_RE = re.compile(r"^[0-9a-fA-F][0-9a-fA-F-]{19,}$")


def _looks_like_identifier(value: str) -> bool:
    """True for opaque IDs (UUIDs, long hex tokens) that make a poor display name."""

    stripped = value.strip()
    return bool(_IDENTIFIER_RE.match(stripped)) and any(
        character.isdigit() for character in stripped
    )


@dataclass(frozen=True)
class ApplicationFiredRule:
    """One fired Application Fraud rule, labeled for display without inventing data.

    Every raw SAS field the rule carried is kept on `.raw`; the other fields only
    decide how to *label* what SAS already returned (see `_rule_display_name`).
    """

    display_name: str
    name_basis: str
    reason: str | None
    fired: bool
    alert: bool
    rule_identifier: str | None
    rule_reference: str | None
    rule_name: str | None
    entity: str | None
    entity_type: str | None
    raw: dict[str, Any]


# Verified against the live Application Fraud runtime by triggering each exact
# business condition end-to-end (Quick Demo 1 and Demo 2) and reading back
# ruleIdentifier/referenceIdentifier on the rule that actually fired. A
# ruleIdentifier is stable per Decision Rule definition in SAS, so this is a
# display-only label on top of data SAS already returned — the raw identifier,
# referenceIdentifier, and alertReason stay available on every row regardless.
# Only entries confirmed this way belong here; do not add a guess.
_VERIFIED_RULE_NAMES: dict[str, str] = {
    "cc5fb2bb-4dba-4828-9ae1-0f30000db36a": "AF_DR_Disbursement_Account_Anomaly",
    "0cfc3922-fe7c-4224-9a2f-c3140ccab1b0": "AF_DR_Shared_Reference_Network",
}


def _rule_display_name(rule: dict[str, Any]) -> tuple[str, str]:
    """Resolve a human-readable name for a fired rule.

    Priority: SAS ruleName -> ruleReference -> a verified ruleIdentifier mapping
    -> an alert-reason style field -> the raw identifier. A ruleName/ruleReference
    candidate is skipped if it looks like an opaque ID itself, since some SAS
    environments repeat the UUID across more than one field.
    """

    for field_name in ("ruleName", "ruleReference"):
        value = rule.get(field_name)
        if isinstance(value, str) and value.strip() and not _looks_like_identifier(value):
            return value.strip(), field_name

    identifier = rule.get("ruleIdentifier")
    if isinstance(identifier, str):
        verified = _VERIFIED_RULE_NAMES.get(identifier.strip())
        if verified:
            return verified, "verified_mapping"

    for field_name in ("alertReason", "ruleReason", "outcomeName"):
        value = rule.get(field_name)
        if isinstance(value, str) and value.strip():
            return value.strip(), field_name

    identifier = (
        rule.get("ruleIdentifier")
        or rule.get("id")
        or rule.get("ruleReference")
        or rule.get("referenceIdentifier")
    )
    identifier_text = str(identifier).strip() if identifier else ""
    if identifier_text:
        return f"Unknown rule ({identifier_text})", "identifier"
    return "Unknown rule", "none"


def extract_application_fired_rules(
    parsed: Any, *, only_fired: bool = True
) -> list[ApplicationFiredRule]:
    """Turn message.sas.rulefired into structured, presentation-ready rows.

    SAS remains authoritative: this only relabels fields already present on each
    rulefired object, it never derives firedFlg/alertFlg or a rule name that SAS
    did not provide.
    """

    root = parsed if isinstance(parsed, dict) else {}
    message = root.get("message", {})
    sas = message.get("sas", {}) if isinstance(message, dict) else {}
    rules = sas.get("rulefired", []) if isinstance(sas, dict) else []
    rules = (
        rules if isinstance(rules, list) else ([rules] if isinstance(rules, dict) else [])
    )

    def flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y"}
        return bool(value)

    results: list[ApplicationFiredRule] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        fired = flag(rule.get("firedFlg"))
        alert = flag(rule.get("alertFlg"))
        # Some SAS response variants carry alertFlg without repeating firedFlg.
        # Keep the row visible whenever either authoritative SAS flag is true;
        # the two raw booleans remain separate on ApplicationFiredRule.
        if only_fired and not (fired or alert):
            continue
        display_name, basis = _rule_display_name(rule)
        reason = rule.get("alertReason") or rule.get("ruleReason")
        results.append(
            ApplicationFiredRule(
                display_name=display_name,
                name_basis=basis,
                reason=(
                    str(reason).strip()
                    if isinstance(reason, str) and reason.strip()
                    else None
                ),
                fired=fired,
                alert=alert,
                rule_identifier=(
                    str(rule.get("ruleIdentifier")).strip()
                    if rule.get("ruleIdentifier")
                    else None
                ),
                rule_reference=(
                    str(rule.get("ruleReference") or rule.get("referenceIdentifier")).strip()
                    if rule.get("ruleReference") or rule.get("referenceIdentifier")
                    else None
                ),
                rule_name=(
                    str(rule.get("ruleName")).strip() if rule.get("ruleName") else None
                ),
                entity=(
                    str(rule.get("outcomeEntity")).strip()
                    if rule.get("outcomeEntity")
                    else None
                ),
                entity_type=(
                    str(rule.get("outcomeEntityType")).strip()
                    if rule.get("outcomeEntityType")
                    else None
                ),
                raw=rule,
            )
        )
    return results


def extract_return_fields(parsed: Any) -> dict[str, Any]:
    """Extract optional return metadata from the response shapes seen in SAS."""

    result = {"returnType": None, "returnDesc": None, "returnDetails": None}
    if not isinstance(parsed, dict):
        return result

    message = parsed.get("message")
    message = message if isinstance(message, dict) else {}
    sas = message.get("sas")
    sas = sas if isinstance(sas, dict) else {}
    system = sas.get("system")
    system = system if isinstance(system, dict) else {}
    response = parsed.get("response")
    response = response if isinstance(response, dict) else {}
    message_response = message.get("response")
    message_response = message_response if isinstance(message_response, dict) else {}
    candidates = (system, parsed, message, sas, response, message_response)
    for field_name in result:
        result[field_name] = next(
            (
                candidate[field_name]
                for candidate in candidates
                if field_name in candidate
            ),
            None,
        )
    return result
