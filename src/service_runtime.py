"""Runtime helpers for the publisher service."""

import asyncio
import signal
from contextlib import suppress

from src.api.polygon import PolygonClient
from src.core.models import TradeData
from src.events.redis_pubsub import RedisTradePublisher
from src.monitor import TradeMonitor
from src.pubsub.topics import TRADE_TOPIC
from src.utils.logging import get_logger

log = get_logger(__name__)


async def listen(
    redis_url: str,
    shutdown_event: asyncio.Event | None = None,
    install_signal_handlers: bool = True,
) -> None:
    """Listen to all Polymarket trades and publish events to Redis."""
    log.info("Tracking ALL Polymarket trades")
    stop_event = shutdown_event or asyncio.Event()
    loop = asyncio.get_running_loop()
    signal_handlers: list[signal.Signals] = []

    def request_shutdown() -> None:
        if not stop_event.is_set():
            log.info("Shutdown requested")
            stop_event.set()

    if install_signal_handlers:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, request_shutdown)
                signal_handlers.append(sig)
            except NotImplementedError:
                continue

    monitor = TradeMonitor()
    publisher = RedisTradePublisher(redis_url=redis_url, channel=TRADE_TOPIC)
    await publisher.connect()
    log.info("Publishing trade events", redis_url=redis_url, channel=TRADE_TOPIC)

    async def on_trade(trade: TradeData) -> None:
        await publisher.publish_trade(trade)

    monitor.on("transaction", on_trade)
    monitor.on("error", lambda e: log.error("Error", error=str(e)))
    monitor.on("close", lambda d: log.warning("Connection closed", details=d))

    monitor_task = asyncio.create_task(monitor.start([]))
    shutdown_task = asyncio.create_task(stop_event.wait())
    try:
        done, _ = await asyncio.wait(
            {monitor_task, shutdown_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if shutdown_task in done and not monitor_task.done():
            monitor_task.cancel()
        with suppress(asyncio.CancelledError):
            await monitor_task
    finally:
        shutdown_task.cancel()
        with suppress(asyncio.CancelledError):
            await shutdown_task
        for sig in signal_handlers:
            loop.remove_signal_handler(sig)
        await monitor.stop()
        await publisher.close()


async def healthcheck(redis_url: str, timeout_seconds: float = 10.0) -> None:
    """Check that the service dependencies are reachable."""
    publisher = RedisTradePublisher(redis_url=redis_url, channel=TRADE_TOPIC)
    polygon_client = PolygonClient()

    try:
        await publisher.connect()
        async with asyncio.timeout(timeout_seconds):
            await polygon_client.connect()
    finally:
        await polygon_client.disconnect()
        await publisher.close()
