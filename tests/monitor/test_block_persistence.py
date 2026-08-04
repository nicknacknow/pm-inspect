"""Tests for persisting the last processed block for resume-on-restart."""

import unittest
from unittest.mock import AsyncMock, patch

from src.events.block_state import LAST_BLOCK_KEY
from src.monitor import TradeMonitor


class _FakeRedis:
    """Minimal async redis stub used as the monitor block-state store."""

    def __init__(self) -> None:
        self._data: dict[str, object] = {}

    async def set(self, key: str, value: object) -> None:
        self._data[key] = value

    async def get(self, key: str):
        return self._data.get(key)


class _FakeClient:
    RECONNECT_DELAY_SECONDS = 0

    def __init__(self, *, latest_block: int = 0) -> None:
        self.latest_block = latest_block
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.subscribe_calls = 0

    async def connect(self) -> None:
        self.connect_calls += 1

    async def disconnect(self) -> None:
        self.disconnect_calls += 1

    async def get_latest_block_number(self) -> int:
        return self.latest_block

    async def subscribe_blocks(self, _callback) -> None:
        self.subscribe_calls += 1


class BlockPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_on_block_persists_block_number_when_state_store_connected(self) -> None:
        monitor = TradeMonitor()
        monitor.block_state = _FakeRedis()
        processor = AsyncMock()
        processor.process_block.return_value = []

        await monitor._on_block(42, processor)

        self.assertEqual(monitor.block_state._data[LAST_BLOCK_KEY], 42)

    async def test_on_block_does_not_persist_without_state_store(self) -> None:
        monitor = TradeMonitor()
        processor = AsyncMock()
        processor.process_block.return_value = []

        await monitor._on_block(42, processor)

        self.assertIsNone(monitor.block_state)

    async def test_start_resumes_from_persisted_block_before_live_subscription(self) -> None:
        monitor = TradeMonitor()
        monitor.client = _FakeClient(latest_block=103)
        monitor.block_state = _FakeRedis()

        with patch("src.monitor.BlockProcessor") as processor_cls:
            processor = AsyncMock()
            processor.process_block.return_value = []
            processor_cls.return_value = processor

            async def on_close(_evt: dict) -> None:
                await monitor.stop()

            monitor.on("close", on_close)

            await monitor.start([], resume_from=99)

        processed = [call.args[0] for call in processor.process_block.await_args_list]
        self.assertEqual(processed, [100, 101, 102, 103])
        self.assertEqual(monitor.client.subscribe_calls, 1)
        self.assertEqual(monitor.block_state._data[LAST_BLOCK_KEY], 103)


if __name__ == "__main__":
    unittest.main()
