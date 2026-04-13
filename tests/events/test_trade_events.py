"""Trade event serialization/deserialization tests."""

import unittest

from src.core.models import TradeData
from src.events.trade_events import deserialize_trade_event, serialize_trade_event


class TradeEventTests(unittest.TestCase):
    def test_trade_event_round_trip(self) -> None:
        original = TradeData(
            block_number=99,
            timestamp="2026-01-02T03:04:05+00:00",
            transaction_hash="0xabcdef1234567890",
            wallet="0x1234567890abcdef1234567890abcdef12345678",
            token_id="999",
            side=0,
            maker_amount=1_000_000,
            taker_amount=2_000_000,
        )

        payload = serialize_trade_event(original)
        restored = deserialize_trade_event(payload)

        self.assertEqual(restored, original)

    def test_deserialize_rejects_invalid_payload(self) -> None:
        invalid_payload = (
            '{"event_type":"trade","event_version":"1.0.0",'
            '"trade":{"block_number":1,"timestamp":"2026-01-01T00:00:00+00:00",'
            '"wallet":"0x1234567890abcdef1234567890abcdef12345678","token_id":"1",'
            '"side":0,"maker_amount":1,"taker_amount":2}}'
        )

        with self.assertRaises(ValueError):
            deserialize_trade_event(invalid_payload)


if __name__ == "__main__":
    unittest.main()
