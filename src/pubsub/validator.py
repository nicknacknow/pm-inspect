"""JSON-schema validation helpers for pub/sub payloads."""

from typing import Any

from jsonschema import ValidationError, Draft202012Validator

from src.pubsub.schema_loader import load_schema
from src.pubsub.topics import TRADE_EVENT_TYPE, TRADE_EVENT_VERSION
from src.metrics import metrics

_TRADE_SCHEMA_PATH = f"polymarket/{TRADE_EVENT_TYPE}/v{TRADE_EVENT_VERSION}/schema.json"
_VALIDATOR: Draft202012Validator | None = None


def _get_validator() -> Draft202012Validator:
    global _VALIDATOR
    if _VALIDATOR is None:
        schema = load_schema(_TRADE_SCHEMA_PATH)
        _VALIDATOR = Draft202012Validator(schema)
    return _VALIDATOR


def validate_trade_event_payload(payload: dict[str, Any]) -> None:
    """Validate a trade event payload against local schema."""
    try:
        _get_validator().validate(payload)
    except ValidationError as exc:
        metrics.trade_event_validation_failures_total.inc()
        raise ValueError(f"trade event schema validation failed: {exc.message}") from exc

