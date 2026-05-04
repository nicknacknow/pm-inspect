"""CLI runtime behavior tests."""

import unittest
from unittest.mock import AsyncMock, patch

from redis.exceptions import ConnectionError as RedisConnectionError
from typer.testing import CliRunner

import src.cli as cli


class CliRuntimeTests(unittest.TestCase):
    def test_listen_shows_tidy_error_when_redis_is_unreachable(self) -> None:
        with patch.object(cli.metrics, "serve") as serve_mock:
            with patch.object(
                cli.RedisTradePublisher,
                "connect",
                new=AsyncMock(side_effect=RedisConnectionError("refused")),
            ):
                result = CliRunner().invoke(cli.app, [])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Could not connect to Redis", result.output)
        self.assertNotIn("Traceback", result.output)
        serve_mock.assert_called_once_with(8001)


if __name__ == "__main__":
    unittest.main()
