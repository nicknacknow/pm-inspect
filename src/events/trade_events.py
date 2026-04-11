"""Trade event serialization/deserialization."""

import json
from dataclasses import asdict

from src.core.models import TradeData
from src.pubsub.topics import TRADE_EVENT_TYPE, TRADE_EVENT_VERSION
from src.pubsub.validator import validate_trade_event_payload


def serialize_trade_event(trade: TradeData) -> str:
    """Serialize a trade event payload."""
    payload = {
        "event_type": TRADE_EVENT_TYPE,
        "event_version": TRADE_EVENT_VERSION,
        "trade": asdict(trade),
    }
    validate_trade_event_payload(payload)
    return json.dumps(payload, separators=(",", ":"))


def deserialize_trade_event(payload: str) -> TradeData:
    """Deserialize a trade event payload into TradeData."""
    decoded = json.loads(payload)
    validate_trade_event_payload(decoded)
    trade = decoded.get("trade")
    if not isinstance(trade, dict):
        raise ValueError("event payload is missing trade object")

    return TradeData(
        block_number=int(trade["block_number"]),
        timestamp=str(trade["timestamp"]),
        transaction_hash=str(trade["transaction_hash"]),
        wallet=str(trade["wallet"]),
        token_id=str(trade["token_id"]),
        side=int(trade["side"]),
        maker_amount=int(trade["maker_amount"]),
        taker_amount=int(trade["taker_amount"]),
    )

