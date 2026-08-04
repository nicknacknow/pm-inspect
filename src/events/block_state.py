"""Persisted block-head state for resume-on-restart."""

from redis.asyncio import Redis

from src.metrics import metrics

LAST_BLOCK_KEY = "pm:inspect:last_block"


async def set_last_block(redis: Redis, block_number: int) -> None:
    """Persist the last successfully processed block number."""
    await redis.set(LAST_BLOCK_KEY, block_number)
    metrics.last_persisted_block.set(block_number)


async def get_last_block(redis: Redis) -> int | None:
    """Return the last persisted block number, or None if never persisted."""
    raw = await redis.get(LAST_BLOCK_KEY)
    if raw is None:
        return None
    return int(raw)
