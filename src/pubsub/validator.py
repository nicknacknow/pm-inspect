"""JSON-schema validation helpers for pub/sub payloads."""

from typing import Any

from jsonschema import ValidationError, validate

from src.pubsub.schema_loader import load_schema

_TRADE_SCHEMA_PATH = "polymarket/trade/v2.0.0/schema.json"


def validate_trade_event_payload(payload: dict[str, Any]) -> None:
    """Validate a trade event payload against local schema."""
    schema = load_schema(_TRADE_SCHEMA_PATH)
    try:
        validate(instance=payload, schema=schema)
    except ValidationError as exc:
        raise ValueError(f"trade event schema validation failed: {exc.message}") from exc

