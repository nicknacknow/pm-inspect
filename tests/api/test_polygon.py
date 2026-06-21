import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import websockets.exceptions

from src.api.polygon import PolygonClient
from src.constants import POLYGON_WSS_URLS


@pytest.fixture(autouse=True)
def _set_urls(monkeypatch):
    monkeypatch.setattr("src.api.polygon.POLYGON_WSS_URLS", [
        "wss://primary",
        "wss://secondary",
        "ws://tertiary",
    ])


class TestDeriveHttpUrl:
    def test_wss_prefix(self):
        assert PolygonClient._derive_http_url("wss://example.com") == "https://example.com"

    def test_ws_prefix(self):
        assert PolygonClient._derive_http_url("ws://example.com") == "http://example.com"

    def test_plain_url_passthrough(self):
        assert PolygonClient._derive_http_url("https://example.com") == "https://example.com"

    def test_trailing_slash_stripped(self):
        assert PolygonClient._derive_http_url("wss://example.com/") == "https://example.com"


class TestPolygonClientInit:
    def test_starts_at_first_endpoint(self):
        client = PolygonClient()
        assert client.wss_url == "wss://primary"
        assert client.http_url == "https://primary"

    def test_raises_without_urls(self, monkeypatch):
        monkeypatch.setattr("src.api.polygon.POLYGON_WSS_URLS", [])
        with pytest.raises(ValueError, match="POLYGON_WSS_URLS"):
            PolygonClient()


class TestEndpointRotation:
    def test_advance_cycles_endpoints(self):
        client = PolygonClient()
        assert client._current_url() == "wss://primary"
        assert client._advance_endpoint() is True
        assert client.wss_url == "wss://secondary"
        assert client.http_url == "https://secondary"
        assert client._advance_endpoint() is True
        assert client.wss_url == "ws://tertiary"
        assert client._advance_endpoint() is True
        assert client.wss_url == "wss://primary"

    def test_advance_noop_on_single_endpoint(self, monkeypatch):
        monkeypatch.setattr("src.api.polygon.POLYGON_WSS_URLS", ["wss://only"])
        client = PolygonClient()
        assert client._advance_endpoint() is False
        assert client.wss_url == "wss://only"


class TestNextId:
    def test_next_id_increments(self):
        client = PolygonClient()
        assert client._next_id() == 1
        assert client._next_id() == 2
        assert client._next_id() == 3


class TestConnectDisconnect:
    def test_disconnect_clears_ws_and_session(self):
        client = PolygonClient()
        client._ws = AsyncMock()
        client._http_session = AsyncMock()

        asyncio.run(client.disconnect())
        assert client._ws is None
        assert client._http_session is None


def _make_ok_response(json_data):
    resp = AsyncMock()
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    resp.json = AsyncMock(return_value=json_data)
    return resp


def _make_fake_http_session(side_effects):
    """Build a fake aiohttp session that returns responses from side_effects."""
    responses = []
    for item in side_effects:
        if item == "CLIENT_ERROR":
            responses.append(aiohttp.ClientError("boom"))
        else:
            responses.append(_make_ok_response(item))

    session = MagicMock()
    session.closed = False
    session.post = MagicMock(side_effect=responses)
    return session


import aiohttp  # noqa: E402


class TestRpcCall:
    def test_returns_result_on_success(self):
        client = PolygonClient()
        client._request_id = 0
        client._http_session = _make_fake_http_session([
            {"jsonrpc": "2.0", "id": 1, "result": "0x1"},
        ])
        result = asyncio.run(client._rpc_call("eth_blockNumber"))
        assert result == "0x1"

    def test_rotates_endpoint_on_client_error_when_multiple_endpoints(self):
        client = PolygonClient()
        client._request_id = 0
        assert client.wss_url == "wss://primary"

        client._http_session = _make_fake_http_session([
            "CLIENT_ERROR",
            {"jsonrpc": "2.0", "id": 2, "result": "0x1"},
        ])

        result = asyncio.run(client._rpc_call("eth_blockNumber"))
        assert result == "0x1"
        assert client.wss_url == "wss://secondary"

    def test_no_rotate_on_client_error_when_single_endpoint(self, monkeypatch):
        monkeypatch.setattr("src.api.polygon.POLYGON_WSS_URLS", ["wss://only"])
        client = PolygonClient()
        client._request_id = 0

        client._http_session = _make_fake_http_session([
            "CLIENT_ERROR",
            {"jsonrpc": "2.0", "id": 2, "result": "0x1"},
        ])

        result = asyncio.run(client._rpc_call("eth_blockNumber"))
        assert result == "0x1"
        assert client.wss_url == "wss://only"

    def test_rotates_endpoint_on_json_decode_error(self):
        client = PolygonClient()
        client._request_id = 0
        assert client.wss_url == "wss://primary"

        bad_resp = MagicMock()
        bad_resp.__aenter__ = AsyncMock(return_value=bad_resp)
        bad_resp.__aexit__ = AsyncMock(return_value=False)
        bad_resp.json = MagicMock(side_effect=json.JSONDecodeError("nope", "", 0))
        good_resp = _make_ok_response({"jsonrpc": "2.0", "id": 2, "result": "0x1"})

        session = MagicMock()
        session.closed = False
        session.post = MagicMock(side_effect=[bad_resp, good_resp])
        client._http_session = session

        result = asyncio.run(client._rpc_call("eth_blockNumber"))
        assert result == "0x1"
        assert client.wss_url == "wss://secondary"

    def test_get_block_with_transactions_calls_eth_getBlockByNumber(self):
        client = PolygonClient()
        client._request_id = 0
        client._http_session = _make_fake_http_session([
            {"jsonrpc": "2.0", "id": 1, "result": {"transactions": []}},
        ])

        result = asyncio.run(client.get_block_with_transactions(123))
        assert result == {"transactions": []}
        called_with = client._http_session.post.call_args
        assert called_with.kwargs["json"]["method"] == "eth_getBlockByNumber"
        assert called_with.kwargs["json"]["params"] == ["0x7b", True]

    def test_get_transaction_receipt_calls_eth_getTransactionReceipt(self):
        client = PolygonClient()
        client._request_id = 0
        client._http_session = _make_fake_http_session([
            {"jsonrpc": "2.0", "id": 1, "result": {"status": "0x1"}},
        ])

        result = asyncio.run(client.get_transaction_receipt("0xabc"))
        assert result == {"status": "0x1"}
        called_with = client._http_session.post.call_args
        assert called_with.kwargs["json"]["method"] == "eth_getTransactionReceipt"
        assert called_with.kwargs["json"]["params"] == ["0xabc"]

    def test_get_block_receipts_calls_eth_getBlockReceipts(self):
        client = PolygonClient()
        client._request_id = 0
        client._http_session = _make_fake_http_session([
            {"jsonrpc": "2.0", "id": 1, "result": [{"txId": 1}]},
        ])

        result = asyncio.run(client.get_block_receipts(42))
        assert result == [{"txId": 1}]
        called_with = client._http_session.post.call_args
        assert called_with.kwargs["json"]["method"] == "eth_getBlockReceipts"
        assert called_with.kwargs["json"]["params"] == ["0x2a"]

    def test_get_block_receipts_returns_empty_list_on_none(self):
        client = PolygonClient()
        client._request_id = 0
        client._http_session = _make_fake_http_session([
            {"jsonrpc": "2.0", "id": 1, "result": None},
        ])

        result = asyncio.run(client.get_block_receipts(42))
        assert result == []


class TestSubscribeBlocks:
    class _Halt(Exception):
        """Used to break out of the infinite subscribe loop during tests."""
        pass

    def test_reconnect_rotates_on_connection_closed(self):
        client = PolygonClient()
        client._ws = AsyncMock()
        client._ws.send = AsyncMock()
        client._ws.close = AsyncMock()

        class AsyncIterDrop:
            def __init__(self):
                self.dropped = False
            def __aiter__(self):
                return self
            async def __anext__(self):
                if not self.dropped:
                    self.dropped = True
                    return json.dumps({"params": {"result": {"number": "0x1"}}}).encode()
                raise ConnectionError("connection dropped")

        client._ws.__aiter__ = MagicMock(return_value=AsyncIterDrop())

        new_ws = AsyncMock()
        new_ws.send = AsyncMock()
        new_ws.recv = AsyncMock(return_value=json.dumps({"result": {}}).encode())
        new_ws.close = AsyncMock()

        class HaltIter:
            def __init__(self, exc):
                self._exc = exc
            def __aiter__(self):
                return self
            async def __anext__(self):
                raise self._exc

        new_ws.__aiter__ = MagicMock(return_value=HaltIter(self._Halt))

        with patch("src.api.polygon.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = [new_ws, new_ws]

            advance_mock = MagicMock(wraps=client._advance_endpoint)
            with patch.object(PolygonClient, "_advance_endpoint", advance_mock):
                with pytest.raises(self._Halt):
                    async def _listen():
                        await client.subscribe_blocks(client._ws.send)
                    asyncio.run(_listen())

            assert advance_mock.call_count >= 1

    def test_raises_on_single_endpoint_connection_closed(self, monkeypatch):
        monkeypatch.setattr("src.api.polygon.POLYGON_WSS_URLS", ["wss://only"])
        client = PolygonClient()
        client._ws = AsyncMock()
        client._ws.send = AsyncMock()
        client._ws.close = AsyncMock()

        class AsyncIterWithError:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise ConnectionError("connection dropped")

        client._ws.__aiter__ = MagicMock(return_value=AsyncIterWithError())

        callback = AsyncMock(side_effect=self._Halt)

        with patch("src.api.polygon.websockets.connect", new_callable=AsyncMock):
            with pytest.raises(ConnectionError):
                async def _listen():
                    await client.subscribe_blocks(callback)
                asyncio.run(_listen())

        assert client._endpoint_index == 0
