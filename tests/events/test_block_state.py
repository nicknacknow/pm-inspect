"""Tests for persisted block-head state (resume-on-restart)."""

import unittest

from src.events.block_state import LAST_BLOCK_KEY, get_last_block, set_last_block
from src.metrics import metrics


class _FakeRedis:
    """Minimal async redis stub with real get/set semantics."""

    def __init__(self) -> None:
        self._data: dict[str, object] = {}

    async def set(self, key: str, value: object) -> None:
        self._data[key] = value

    async def get(self, key: str):
        return self._data.get(key)


class BlockStateTests(unittest.IsolatedAsyncioTestCase):
    async def test_set_last_block_roundtrip(self) -> None:
        redis = _FakeRedis()

        await set_last_block(redis, 42)
        stored = await get_last_block(redis)

        self.assertEqual(stored, 42)
        self.assertEqual(redis._data[LAST_BLOCK_KEY], 42)

    async def test_get_last_block_returns_none_when_never_persisted(self) -> None:
        redis = _FakeRedis()

        self.assertIsNone(await get_last_block(redis))

    async def test_set_last_block_updates_last_persisted_gauge(self) -> None:
        redis = _FakeRedis()

        await set_last_block(redis, 123)

        self.assertEqual(metrics.last_persisted_block._value.get(), 123.0)


if __name__ == "__main__":
    unittest.main()
