"""Runtime tests for CLI reliability helpers."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import typer

import src.cli as cli


class CliRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def test_validate_polygon_wss_url_requires_value(self) -> None:
        with patch("src.cli.POLYGON_WSS_URL", None):
            with self.assertRaises(typer.Exit) as ctx:
                cli._validate_polygon_wss_url()
        self.assertEqual(ctx.exception.exit_code, 1)

    def test_validate_polygon_wss_url_requires_ws_scheme(self) -> None:
        with patch("src.cli.POLYGON_WSS_URL", "https://example.com"):
            with self.assertRaises(typer.Exit) as ctx:
                cli._validate_polygon_wss_url()
        self.assertEqual(ctx.exception.exit_code, 1)

    async def test_check_connects_and_closes_redis(self) -> None:
        publisher = AsyncMock()
        with (
            patch("src.cli.POLYGON_WSS_URL", "wss://example.com"),
            patch("src.cli.RedisTradePublisher", return_value=publisher),
        ):
            await cli._check("redis://redis:6379/0")

        publisher.connect.assert_awaited_once()
        publisher.close.assert_awaited_once()

    async def test_listen_stops_monitor_on_shutdown_signal(self) -> None:
        class FakeMonitor:
            def __init__(self) -> None:
                self.callbacks: dict[str, list] = {"transaction": [], "error": [], "close": []}
                self.stop_called = False

            def on(self, event: str, callback) -> None:
                self.callbacks[event].append(callback)

            async def start(self, target_wallets: list[str]) -> None:
                await asyncio.Event().wait()

            async def stop(self) -> None:
                self.stop_called = True

        fake_monitor = FakeMonitor()
        publisher = AsyncMock()

        def trigger_shutdown(stop_event: asyncio.Event) -> None:
            stop_event.set()

        with (
            patch("src.cli.POLYGON_WSS_URL", "wss://example.com"),
            patch("src.cli.TradeMonitor", return_value=fake_monitor),
            patch("src.cli.RedisTradePublisher", return_value=publisher),
            patch("src.cli._install_signal_handlers", side_effect=trigger_shutdown),
        ):
            await cli._listen("redis://redis:6379/0")

        self.assertTrue(fake_monitor.stop_called)
        publisher.connect.assert_awaited_once()
        publisher.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
