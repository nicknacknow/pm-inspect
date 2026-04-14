"""CLI for pminspect publisher service."""

import asyncio
from collections.abc import Awaitable, Callable

import typer
from redis.exceptions import ConnectionError as RedisConnectionError
from websockets.exceptions import WebSocketException

from src.constants import REDIS_URL
from src import service_runtime
from src.utils.logging import get_logger

app = typer.Typer(
    name="pminspect",
    help="Publish Polymarket trades to Redis Pub/Sub",
)

log = get_logger(__name__)

_listen = service_runtime.listen
_healthcheck = service_runtime.healthcheck


@app.command()
def listen(
    redis_url: str = typer.Option(
        REDIS_URL,
        "--redis-url",
        help="Redis URL for trade event publishing",
    ),
) -> None:
    """Listen to all Polymarket trades and publish events to Redis."""
    _run_command(
        lambda: _listen(redis_url=redis_url),
        redis_url=redis_url,
        failure_label="Startup validation failed",
    )


@app.command()
def healthcheck(
    redis_url: str = typer.Option(
        REDIS_URL,
        "--redis-url",
        help="Redis URL for connectivity checks",
    ),
) -> None:
    """Verify Redis and Polygon connectivity before starting the service."""
    _run_command(
        lambda: _healthcheck(redis_url=redis_url),
        redis_url=redis_url,
        failure_label="Healthcheck failed",
    )
    typer.echo("OK: Redis and Polygon are reachable.")


def _run_command(
    command: Callable[[], Awaitable[None]],
    *,
    redis_url: str,
    failure_label: str,
) -> None:
    try:
        asyncio.run(command())
    except RedisConnectionError as exc:
        log.error("Redis connection failed", redis_url=redis_url, error=str(exc))
        typer.echo(
            "ERROR: Could not connect to Redis. "
            "Start Redis and/or set --redis-url to a reachable instance.",
            err=True,
        )
        raise typer.Exit(code=1) from exc
    except (OSError, TimeoutError, ValueError, WebSocketException) as exc:
        log.error(failure_label, error=str(exc))
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
