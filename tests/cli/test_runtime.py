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
        self.start_cancelled = False
        self._released = asyncio.Event()

    def on(self, event: str, callback) -> None:
        self.callbacks[event] = callback

    async def start(self, target_wallets: list[str]) -> None:
        self.start_wallets = target_wallets
        try:
            await self._released.wait()
        except asyncio.CancelledError:
            self.start_cancelled = True
            raise

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
        self.assertTrue(fake_monitor.start_cancelled)
        fake_publisher.connect.assert_awaited_once()
        fake_publisher.close.assert_awaited_once()

    async def test_listen_cleans_up_when_publisher_connect_fails(self) -> None:
        fake_monitor = FakeMonitor()
        fake_publisher = AsyncMock()
        fake_publisher.connect.side_effect = RuntimeError("boom")

        with patch.object(runtime, "TradeMonitor", return_value=fake_monitor), patch.object(
            runtime, "RedisTradePublisher", return_value=fake_publisher
        ):
            with self.assertRaises(RuntimeError):
                await runtime.listen(
                    "redis://localhost:6379/0",
                    install_signal_handlers=False,
                )

        self.assertEqual(fake_monitor.stop_calls, 0)
        self.assertIsNone(fake_monitor.start_wallets)
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

    async def test_healthcheck_times_out_when_redis_connect_hangs(self) -> None:
        async def hang() -> None:
            await asyncio.Event().wait()

        publisher_close_mock = AsyncMock()
        polygon_disconnect_mock = AsyncMock()

        with patch.object(
            runtime.RedisTradePublisher,
            "connect",
            new=AsyncMock(side_effect=hang),
        ), patch.object(
            runtime.RedisTradePublisher,
            "close",
            new=publisher_close_mock,
        ), patch.object(
            runtime.PolygonClient,
            "connect",
            new=AsyncMock(),
        ), patch.object(
            runtime.PolygonClient,
            "disconnect",
            new=polygon_disconnect_mock,
        ):
            with self.assertRaises(TimeoutError):
                await runtime.healthcheck(
                    "redis://localhost:6379/0",
                    timeout_seconds=0.01,
                )

        publisher_close_mock.assert_awaited_once()
        polygon_disconnect_mock.assert_awaited_once()

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

    async def test_trade_monitor_stop_while_starting_disconnects_once(self) -> None:
        monitor = monitor_module.TradeMonitor()
        release = asyncio.Event()

        monitor.client.connect = AsyncMock()

        async def wait_for_release(callback) -> None:
            await release.wait()

        async def disconnect_and_release() -> None:
            release.set()

        monitor.client.subscribe_blocks = AsyncMock(side_effect=wait_for_release)
        monitor.client.disconnect = AsyncMock(side_effect=disconnect_and_release)

        start_task = asyncio.create_task(monitor.start([]))
        await asyncio.sleep(0)
        await monitor.stop()
        await start_task

        monitor.client.disconnect.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
