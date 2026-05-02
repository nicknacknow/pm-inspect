"""Tests for Polygon client subscription behavior."""

import json
import unittest
from unittest.mock import AsyncMock, call

from src.api.polygon import PolygonClient


class FakeWebSocket:
    def __init__(self, messages: list[str]) -> None:
        self._messages = iter(messages)
        self.sent_messages: list[str] = []

    async def send(self, message: str) -> None:
        self.sent_messages.append(message)

    async def recv(self) -> str:
        return "{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":1}"

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        try:
            return next(self._messages)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class PolygonClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_subscribe_blocks_catches_up_then_continues_streaming(self) -> None:
        client = PolygonClient("wss://example.invalid")
        client._ws = FakeWebSocket(
            [json.dumps({"params": {"result": {"number": "0x6"}}})]
        )
        client.get_latest_block_number = AsyncMock(return_value=5)

        callback = AsyncMock()

        await client.subscribe_blocks(callback, last_processed_block=2)

        callback.assert_has_awaits([call(3), call(4), call(5), call(6)])
        client.get_latest_block_number.assert_awaited_once()
        self.assertEqual(len(client._ws.sent_messages), 1)


if __name__ == "__main__":
    unittest.main()