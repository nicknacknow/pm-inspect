"""Tests for Redis Pub/Sub publishing."""

import unittest
from unittest.mock import AsyncMock, patch

from src.core.models import TradeData
from src.events.redis_pubsub import RedisTradePublisher


def make_trade() -> TradeData:
    return TradeData(
        block_number=99,
        timestamp="2026-01-02T03:04:05+00:00",
        transaction_hash="0xabcdef1234567890",
        wallet="0x1234567890abcdef1234567890abcdef12345678",
        token_id="999",
        condition_id="0x" + "11" * 32,
        side=0,
        maker_amount=1_000_000,
        taker_amount=2_000_000,
    )


class RedisTradePublisherTests(unittest.IsolatedAsyncioTestCase):
    async def test_publish_trade_requires_connection(self) -> None:
        publisher = RedisTradePublisher("redis://localhost:6379/0", "trades.raw")

        with self.assertRaises(RuntimeError):
            await publisher.publish_trade(make_trade())

    @patch("src.events.redis_pubsub.Redis.from_url")
    @patch(
        "src.events.redis_pubsub.serialize_trade_event",
        return_value='{"event_type":"trade","event_version":"2.0.0"}',
    )
    async def test_connect_publish_and_close(self, serialize_mock, from_url_mock) -> None:
        redis_client = AsyncMock()
        from_url_mock.return_value = redis_client

        publisher = RedisTradePublisher("redis://localhost:6379/0", "trades.raw")
        trade = make_trade()

        await publisher.connect()
        redis_client.ping.assert_awaited_once()

        await publisher.publish_trade(trade)
        serialize_mock.assert_called_once_with(trade)
        redis_client.publish.assert_awaited_once_with("trades.raw", serialize_mock.return_value)

        await publisher.close()
        redis_client.aclose.assert_awaited_once()
        self.assertIsNone(publisher._redis)


if __name__ == "__main__":
    unittest.main()
