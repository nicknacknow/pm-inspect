"""CLI for pminspect publisher service."""

import asyncio

import typer
from redis.exceptions import ConnectionError as RedisConnectionError

from src.constants import METRICS_PORT, REDIS_URL
from src.core.models import TradeData
from src.events.redis_pubsub import RedisTradePublisher
from src.monitor import TradeMonitor
from src.metrics import metrics
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
    metrics_port: int = typer.Option(
        METRICS_PORT,
        "--metrics-port",
        envvar="METRICS_PORT",
        help="Prometheus metrics port",
    ),
) -> None:
    """Listen to all Polymarket trades and publish events to Redis."""
    log.info("Tracking ALL Polymarket trades")
    metrics.serve(metrics_port)
    log.info("Prometheus metrics server started", port=metrics_port)
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


async def _listen(redis_url: str) -> None:
    """Async implementation of listen command."""
    monitor = TradeMonitor()
    publisher = RedisTradePublisher(redis_url=redis_url, channel=TRADE_TOPIC)
    await publisher.connect()
    log.info("Publishing trade events", redis_url=redis_url, channel=TRADE_TOPIC)

    async def on_trade(trade: TradeData) -> None:
        await publisher.publish_trade(trade)

    monitor.on("transaction", on_trade)
    monitor.on("error", lambda e: log.error("Error", error=str(e)))
    monitor.on("close", lambda d: log.warning("Connection closed", details=d))

    try:
        await monitor.start([])
    finally:
        await publisher.close()


if __name__ == "__main__":
    app()
