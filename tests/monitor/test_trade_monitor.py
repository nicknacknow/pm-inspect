"""Tests for TradeMonitor event dispatch and reconnect behavior."""

import unittest

from src.monitor import TradeMonitor


class _FakeClient:
    RECONNECT_DELAY_SECONDS = 0

    def __init__(self, *, subscribe_error: Exception | None = None) -> None:
        self.subscribe_error = subscribe_error
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.subscribe_calls = 0

    async def connect(self) -> None:
        self.connect_calls += 1

    async def disconnect(self) -> None:
        self.disconnect_calls += 1

    async def subscribe_blocks(self, _callback):
        self.subscribe_calls += 1
        if self.subscribe_error:
            raise self.subscribe_error
        return None


class TradeMonitorTests(unittest.IsolatedAsyncioTestCase):
    async def test_emit_calls_sync_and_async_handlers(self) -> None:
        monitor = TradeMonitor()

        sync_calls: list[object] = []
        async_calls: list[object] = []

        def sync_handler(data):
            sync_calls.append(data)

        async def async_handler(data):
            async_calls.append(data)

        monitor.on("transaction", sync_handler)
        monitor.on("transaction", async_handler)

        payload = {"x": 1}
        await monitor.emit("transaction", payload)

        self.assertEqual(sync_calls, [payload])
        self.assertEqual(async_calls, [payload])

    async def test_emit_catches_handler_exception_and_emits_error(self) -> None:
        monitor = TradeMonitor()

        captured: list[Exception] = []

        def bad_handler(_data):
            raise ValueError("boom")

        async def error_handler(exc: Exception):
            captured.append(exc)

        monitor.on("transaction", bad_handler)
        monitor.on("error", error_handler)

        await monitor.emit("transaction", {"x": 1})

        self.assertEqual(len(captured), 1)
        self.assertIsInstance(captured[0], ValueError)

    async def test_start_emits_close_and_can_stop_via_close_handler(self) -> None:
        monitor = TradeMonitor()
        monitor.client = _FakeClient()

        close_events: list[dict] = []

        async def on_close(evt: dict) -> None:
            close_events.append(evt)
            await monitor.stop()

        monitor.on("close", on_close)

        await monitor.start(["0x" + "11" * 20])

        self.assertGreaterEqual(monitor.client.connect_calls, 1)
        self.assertGreaterEqual(monitor.client.subscribe_calls, 1)
        self.assertEqual(len(close_events), 1)
        self.assertEqual(close_events[0]["code"], 1000)

    async def test_start_on_subscribe_error_emits_error_and_close(self) -> None:
        monitor = TradeMonitor()
        monitor.client = _FakeClient(subscribe_error=RuntimeError("sub failed"))

        errors: list[Exception] = []
        closes: list[dict] = []

        async def on_error(exc: Exception) -> None:
            errors.append(exc)

        async def on_close(evt: dict) -> None:
            closes.append(evt)
            await monitor.stop()

        monitor.on("error", on_error)
        monitor.on("close", on_close)

        await monitor.start(["0x" + "11" * 20])

        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RuntimeError)
        self.assertEqual(len(closes), 1)
        self.assertEqual(closes[0]["code"], -1)


if __name__ == "__main__":
    unittest.main()
