"""CLI for pminspect publisher service."""

import asyncio
import contextlib
import signal

import typer
from redis.exceptions import ConnectionError as RedisConnectionError

from src.constants import POLYGON_WSS_URL, REDIS_URL
from src.core.models import TradeData
from src.events.redis_pubsub import RedisTradePublisher
from src.monitor import TradeMonitor
from src.pubsub.topics import TRADE_TOPIC
from src.utils.logging import get_logger

app = typer.Typer(
    name="pminspect",
    help="Publish Polymarket trades to Redis Pub/Sub",
)

log = get_logger(__name__)

@app.command()
def listen(
    redis_url: str = typer.Option(
        REDIS_URL,
        "--redis-url",
        help="Redis URL for trade event publishing",
    ),
) -> None:
    """Listen to all Polymarket trades and publish events to Redis."""
    log.info("Tracking ALL Polymarket trades")
    try:
        asyncio.run(_listen(redis_url=redis_url))
    except RedisConnectionError as exc:
        log.error("Redis connection failed", redis_url=redis_url, error=str(exc))
        typer.echo(
            "ERROR: Could not connect to Redis. "
            "Start Redis and/or set --redis-url to a reachable instance.",
            err=True,
        )
        raise typer.Exit(code=1) from exc


@app.command("check")
def check(
    redis_url: str = typer.Option(
        REDIS_URL,
        "--redis-url",
        help="Redis URL for connectivity check",
    ),
) -> None:
    """Validate required configuration and Redis connectivity."""
    asyncio.run(_check(redis_url=redis_url))


async def _check(redis_url: str) -> None:
    """Async implementation of check command."""
    _validate_polygon_wss_url()
    publisher = RedisTradePublisher(redis_url=redis_url, channel=TRADE_TOPIC)
    await publisher.connect()
    await publisher.close()
    log.info("Health check passed", redis_url=redis_url)
    typer.echo("OK: configuration and Redis connectivity validated.")


def _validate_polygon_wss_url() -> str:
    """Validate POLYGON_WSS_URL presence and basic format."""
    wss_url = (POLYGON_WSS_URL or "").strip()
    if not wss_url:
        typer.echo("ERROR: POLYGON_WSS_URL is required.", err=True)
        raise typer.Exit(code=1)
    if not (wss_url.startswith("wss://") or wss_url.startswith("ws://")):
        typer.echo("ERROR: POLYGON_WSS_URL must start with ws:// or wss://.", err=True)
        raise typer.Exit(code=1)
    return wss_url


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    """Install SIGINT/SIGTERM handlers to trigger graceful shutdown."""
    loop = asyncio.get_running_loop()

    def _on_signal(sig: signal.Signals) -> None:
        log.info("Shutdown signal received", signal=sig.name)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _on_signal, sig)


async def _listen(redis_url: str) -> None:
    """Async implementation of listen command."""
    _validate_polygon_wss_url()
    monitor = TradeMonitor()
    publisher = RedisTradePublisher(redis_url=redis_url, channel=TRADE_TOPIC)
    await publisher.connect()
    log.info("Publishing trade events", redis_url=redis_url, channel=TRADE_TOPIC)
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)

    async def on_trade(trade: TradeData) -> None:
        await publisher.publish_trade(trade)

    def on_close(details: dict) -> None:
        log.warning("Connection closed", details=details)
        stop_event.set()

    monitor.on("transaction", on_trade)
    monitor.on("error", lambda e: log.error("Error", error=str(e)))
    monitor.on("close", on_close)

    monitor_task = asyncio.create_task(monitor.start([]))
    stop_task = asyncio.create_task(stop_event.wait())
    try:
        done, _ = await asyncio.wait(
            {monitor_task, stop_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if monitor_task in done:
            await monitor_task
        else:
            await monitor.stop()
            monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await monitor_task
    finally:
        stop_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await stop_task
        await publisher.close()


if __name__ == "__main__":
    app()
