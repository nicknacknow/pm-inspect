"""Tests for Polygon client endpoint fallback."""

import unittest
from unittest.mock import AsyncMock, Mock, patch

import src.api.polygon as polygon_module
import src.constants as constants
from src.api.polygon import PolygonClient


class PolygonClientTests(unittest.IsolatedAsyncioTestCase):
    def test_parse_env_urls_splits_comma_and_newline_separated_values(self) -> None:
        self.assertEqual(
            constants._parse_env_urls(
                "wss://one.example,\n wss://two.example , ,wss://three.example"
            ),
            (
                "wss://one.example",
                "wss://two.example",
                "wss://three.example",
            ),
        )

    async def test_connect_tries_polygon_endpoints_in_order(self) -> None:
        fake_ws = AsyncMock()
        fake_ssl_context = Mock()

        with patch.object(
            polygon_module,
            "POLYGON_WSS_URLS",
            ("wss://bad.example", "wss://good.example"),
        ), patch.object(polygon_module, "POLYGON_WSS_URL", None), patch.object(
            polygon_module.ssl,
            "create_default_context",
            return_value=fake_ssl_context,
        ), patch.object(
            polygon_module.websockets,
            "connect",
            new=AsyncMock(side_effect=[OSError("first down"), fake_ws]),
        ) as connect_mock:
            client = PolygonClient()
            await client.connect()

        self.assertEqual(client.wss_url, "wss://good.example")
        self.assertEqual(client.http_url, "https://good.example")
        self.assertEqual(connect_mock.await_count, 2)
        self.assertEqual(connect_mock.await_args_list[0].args[0], "wss://bad.example")
        self.assertEqual(connect_mock.await_args_list[1].args[0], "wss://good.example")

    async def test_connect_raises_when_all_polygon_endpoints_fail(self) -> None:
        with patch.object(
            polygon_module,
            "POLYGON_WSS_URLS",
            ("wss://bad.example", "wss://worse.example"),
        ), patch.object(polygon_module, "POLYGON_WSS_URL", None), patch.object(
            polygon_module.ssl,
            "create_default_context",
            return_value=Mock(),
        ), patch.object(
            polygon_module.websockets,
            "connect",
            new=AsyncMock(side_effect=[OSError("first down"), OSError("second down")]),
        ):
            client = PolygonClient()

            with self.assertRaises(ConnectionError) as ctx:
                await client.connect()

        self.assertIn("bad.example", str(ctx.exception))
        self.assertIn("worse.example", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
