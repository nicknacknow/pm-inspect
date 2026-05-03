"""Redis Pub/Sub transport for trade events."""

from time import perf_counter

from redis.asyncio import Redis

from src.core.models import TradeData
from src.events.trade_events import serialize_trade_event
from src.metrics import metrics


class RedisTradePublisher:
    """Publishes trade events to a Redis channel."""

    def __init__(self, redis_url: str, channel: str) -> None:
        self.redis_url = redis_url
        self.channel = channel
        self._redis: Redis | None = None

    async def connect(self) -> None:
        self._redis = Redis.from_url(self.redis_url, decode_responses=True)
        await self._redis.ping()
        metrics.redis_connected.set(1)

    async def publish_trade(self, trade: TradeData) -> None:
        if self._redis is None:
            raise RuntimeError("publisher not connected")

        payload = serialize_trade_event(trade)
        started_at = perf_counter()
        try:
            await self._redis.publish(self.channel, payload)
        except Exception:
            metrics.trade_publish_failures_total.inc()
            raise
        else:
            metrics.trades_published_total.inc()
        finally:
            metrics.trade_publish_seconds.observe(perf_counter() - started_at)

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        metrics.redis_connected.set(0)

