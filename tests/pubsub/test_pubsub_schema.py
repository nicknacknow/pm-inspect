"""Tests for pub/sub schema loading and validation."""

import unittest

from src.pubsub.schema_loader import load_schema
from src.pubsub.validator import validate_trade_event_payload


class PubSubSchemaTests(unittest.TestCase):
    def test_load_schema_reads_bundled_trade_schema(self) -> None:
        schema = load_schema("polymarket/trade/v1.0.0/schema.json")

        self.assertEqual(schema["title"], "polymarket.trade.v1.0.0")
        self.assertFalse(schema["additionalProperties"])

    def test_load_schema_missing_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_schema("polymarket/trade/v1.0.0/missing.json")

    def test_validate_trade_event_payload_accepts_valid_payload(self) -> None:
        payload = {
            "event_type": "trade",
            "event_version": "1.0.0",
            "trade": {
                "block_number": 1,
                "timestamp": "2026-01-01T00:00:00+00:00",
                "transaction_hash": "0xabcdef",
                "wallet": "0x1234567890abcdef1234567890abcdef12345678",
                "token_id": "1",
                "side": 0,
                "maker_amount": 1,
                "taker_amount": 2,
            },
        }

        validate_trade_event_payload(payload)

    def test_validate_trade_event_payload_rejects_extra_trade_fields(self) -> None:
        payload = {
            "event_type": "trade",
            "event_version": "1.0.0",
            "trade": {
                "block_number": 1,
                "timestamp": "2026-01-01T00:00:00+00:00",
                "transaction_hash": "0xabcdef",
                "wallet": "0x1234567890abcdef1234567890abcdef12345678",
                "token_id": "1",
                "side": 0,
                "maker_amount": 1,
                "taker_amount": 2,
                "unexpected": True,
            },
        }

        with self.assertRaises(ValueError):
            validate_trade_event_payload(payload)


if __name__ == "__main__":
    unittest.main()
