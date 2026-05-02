"""Tests for trade monitor lifecycle."""

import asyncio
import unittest
from unittest.mock import AsyncMock

from src.monitor import TradeMonitor


class TradeMonitorTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_reconnects_and_preserves_last_block_number(self) -> None:
        monitor = TradeMonitor()

        monitor.client.connect = AsyncMock()
        monitor.client.disconnect = AsyncMock()
        monitor.client.RECONNECT_DELAY_SECONDS = 0

        async def fake_on_block(block_number: int, processor) -> None:
            monitor._last_block_number = block_number

        monitor._on_block = AsyncMock(side_effect=fake_on_block)

        subscribe_calls = 0

        async def fake_subscribe_blocks(callback, last_processed_block=None) -> None:
            nonlocal subscribe_calls
            subscribe_calls += 1

            if subscribe_calls == 1:
                self.assertIsNone(last_processed_block)
                await callback(123)
                raise RuntimeError("no close frame received or sent")

            self.assertEqual(last_processed_block, 123)
            raise asyncio.CancelledError()

        monitor.client.subscribe_blocks = AsyncMock(side_effect=fake_subscribe_blocks)

        with self.assertRaises(asyncio.CancelledError):
            await monitor.start([])

        self.assertEqual(monitor._last_block_number, 123)
        self.assertEqual(monitor.client.connect.await_count, 2)
        self.assertEqual(monitor.client.disconnect.await_count, 2)
        self.assertEqual(monitor.client.subscribe_blocks.await_count, 2)


if __name__ == "__main__":
    unittest.main()