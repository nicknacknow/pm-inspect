"""Redis Pub/Sub transport for trade events."""

from redis.asyncio import Redis

from src.core.models import TradeData
from src.events.trade_events import serialize_trade_event


class RedisTradePublisher:
    """Publishes trade events to a Redis channel."""

    def __init__(self, redis_url: str, channel: str) -> None:
        self.redis_url = redis_url
        self.channel = channel
        self._redis: Redis | None = None

    async def connect(self) -> None:
        self._redis = Redis.from_url(self.redis_url, decode_responses=True)
        await self._redis.ping()

    async def publish_trade(self, trade: TradeData) -> None:
        if self._redis is None:
            raise RuntimeError("publisher not connected")

        payload = serialize_trade_event(trade)
        await self._redis.publish(self.channel, payload)

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

