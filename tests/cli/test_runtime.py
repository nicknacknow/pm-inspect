"""CLI runtime behavior tests."""

import asyncio
import unittest
from contextlib import suppress
from unittest.mock import AsyncMock, patch

from redis.exceptions import ConnectionError as RedisConnectionError
from typer.testing import CliRunner

import src.cli as cli
import src.service_runtime as runtime
import src.monitor as monitor_module


class CliRuntimeTests(unittest.TestCase):
    def test_listen_shows_tidy_error_when_redis_is_unreachable(self) -> None:
        with patch.object(
            cli,
            "_listen",
            new=AsyncMock(side_effect=RedisConnectionError("refused")),
        ):
            result = CliRunner().invoke(cli.app, ["listen"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Could not connect to Redis", result.output)
        self.assertNotIn("Traceback", result.output)

    def test_listen_command_dispatches_to_runtime_helper(self) -> None:
        with patch.object(cli, "_listen", new=AsyncMock(return_value=None)) as listen_mock:
            result = CliRunner().invoke(
                cli.app,
                ["listen", "--redis-url", "redis://example:6379/0"],
            )

        self.assertEqual(result.exit_code, 0)
        listen_mock.assert_awaited_once_with(redis_url="redis://example:6379/0")

    def test_healthcheck_command_dispatches_to_runtime_helper(self) -> None:
        with patch.object(
            cli, "_healthcheck", new=AsyncMock(return_value=None)
        ) as healthcheck_mock:
            result = CliRunner().invoke(
                cli.app,
                ["healthcheck", "--redis-url", "redis://example:6379/0"],
            )

        self.assertEqual(result.exit_code, 0)
        healthcheck_mock.assert_awaited_once_with(redis_url="redis://example:6379/0")
        self.assertIn("OK: Redis and Polygon are reachable.", result.output)


class FakeMonitor:
    def __init__(self) -> None:
        self.callbacks: dict[str, object] = {}
        self.start_wallets: list[str] | None = None
        self.stop_calls = 0
        self._released = asyncio.Event()

    def on(self, event: str, callback) -> None:
        self.callbacks[event] = callback

    async def start(self, target_wallets: list[str]) -> None:
        self.start_wallets = target_wallets
        await self._released.wait()

    async def stop(self) -> None:
        self.stop_calls += 1
        self._released.set()


class CliRuntimeAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_listen_stops_cleanly_when_shutdown_is_requested(self) -> None:
        fake_monitor = FakeMonitor()
        fake_publisher = AsyncMock()

        async def request_shutdown() -> None:
            await asyncio.sleep(0)
            shutdown_event.set()

        shutdown_event = asyncio.Event()

        with patch.object(runtime, "TradeMonitor", return_value=fake_monitor), patch.object(
            runtime, "RedisTradePublisher", return_value=fake_publisher
        ):
            shutdown_task = asyncio.create_task(request_shutdown())
            try:
                await runtime.listen(
                    "redis://localhost:6379/0",
                    shutdown_event=shutdown_event,
                    install_signal_handlers=False,
                )
            finally:
                shutdown_task.cancel()
                with suppress(asyncio.CancelledError):
                    await shutdown_task

        self.assertEqual(fake_monitor.start_wallets, [])
        self.assertEqual(fake_monitor.stop_calls, 1)
        fake_publisher.connect.assert_awaited_once()
        fake_publisher.close.assert_awaited_once()

    async def test_healthcheck_succeeds_when_dependencies_are_reachable(self) -> None:
        with patch.object(
            runtime.RedisTradePublisher,
            "connect",
            new=AsyncMock(),
        ), patch.object(
            runtime.RedisTradePublisher,
            "close",
            new=AsyncMock(),
        ), patch.object(
            runtime.PolygonClient,
            "connect",
            new=AsyncMock(),
        ), patch.object(
            runtime.PolygonClient,
            "disconnect",
            new=AsyncMock(),
        ):
            await runtime.healthcheck("redis://localhost:6379/0")

    async def test_healthcheck_reports_polygon_connectivity_failures(self) -> None:
        with patch.object(
            runtime.RedisTradePublisher,
            "connect",
            new=AsyncMock(),
        ), patch.object(
            runtime.RedisTradePublisher,
            "close",
            new=AsyncMock(),
        ), patch.object(
            runtime.PolygonClient,
            "connect",
            new=AsyncMock(side_effect=OSError("unreachable")),
        ), patch.object(
            runtime.PolygonClient,
            "disconnect",
            new=AsyncMock(),
        ):
            with self.assertRaises(OSError):
                await runtime.healthcheck("redis://localhost:6379/0")

    def test_healthcheck_command_shows_tidy_error(self) -> None:
        with patch.object(
            cli,
            "_healthcheck",
            new=AsyncMock(side_effect=OSError("unreachable")),
        ):
            result = CliRunner().invoke(cli.app, ["healthcheck"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("unreachable", result.output)

    async def test_trade_monitor_stop_is_idempotent(self) -> None:
        monitor = monitor_module.TradeMonitor()
        monitor.client.disconnect = AsyncMock()
        monitor._running = True

        await monitor.stop()
        await monitor.stop()

        monitor.client.disconnect.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
