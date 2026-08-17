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

    rules = rules if isinstance(rules, list) else []
    alerted = alerted if isinstance(alerted, list) else []
    fired_rules = [rule for rule in rules if isinstance(rule, dict) and rule.get("firedFlg")]

    return SasDecisionSummary(
        message_identifier=system.get("messageIdentifier"),
        transaction_identifier=system.get("transactionIdentifier"),
        outcome=decision.get("outcome"),
        outcome_name=decision.get("outcomeName"),
        reference_identifier=decision.get("referenceIdentifier"),
        alert_created=bool(alerted) or any(rule.get("alertFlg") for rule in fired_rules),
        alerted_entities=[item for item in alerted if isinstance(item, dict)],
        fired_rules=fired_rules,
        evaluated_rule_count=len(rules),
        timings=timings if isinstance(timings, dict) else {},
    )
