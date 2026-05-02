"""Tests for trade monitor lifecycle."""

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from src.monitor import TradeMonitor


class TradeMonitorTests(unittest.IsolatedAsyncioTestCase):
    async def test_on_block_waits_for_transaction_callbacks_before_checkpoint(
        self,
    ) -> None:
        monitor = TradeMonitor()
        processor = Mock()
        processor.process_block = AsyncMock(return_value=[object()])

        callback_started = asyncio.Event()
        callback_release = asyncio.Event()
        observed_last_block_numbers: list[int | None] = []

        async def on_trade(trade) -> None:
            observed_last_block_numbers.append(monitor._last_block_number)
            callback_started.set()
            await callback_release.wait()
            observed_last_block_numbers.append(monitor._last_block_number)

        monitor.on("transaction", on_trade)

        task = asyncio.create_task(monitor._on_block(123, processor))

        await callback_started.wait()
        self.assertIsNone(monitor._last_block_number)

        callback_release.set()
        await task

        self.assertEqual(monitor._last_block_number, 123)
        self.assertEqual(observed_last_block_numbers, [None, None])
        processor.process_block.assert_awaited_once_with(123)

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