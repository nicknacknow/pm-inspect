"""Polygon blockchain client."""
import asyncio
import json
import ssl
from typing import Any, Awaitable, Callable, Optional

import aiohttp
import websockets

from src.constants import POLYGON_WSS_URLS
from src.metrics import metrics
from src.utils.logging import get_logger

log = get_logger(__name__)


class PolygonClient:
    """Manages WebSocket connection to Polygon blockchain via JSON-RPC."""

    RECONNECT_DELAY_SECONDS = 5
    RPC_RETRY_DELAY_SECONDS = 1

    def __init__(self) -> None:
        if not POLYGON_WSS_URLS:
            raise ValueError("POLYGON_WSS_URLS is not configured")
        self._endpoints: list[str] = list(POLYGON_WSS_URLS)
        self._endpoint_index = 0
        self.wss_url = self._current_url()
        self.http_url = self.wss_url.replace("wss://", "https://").rstrip("/")
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._request_id = 0

    def _current_url(self) -> str:
        return self._endpoints[self._endpoint_index % len(self._endpoints)]

    def _advance_endpoint(self) -> bool:
        if len(self._endpoints) <= 1:
            return False
        self._endpoint_index = (self._endpoint_index + 1) % len(self._endpoints)
        previous = self.wss_url
        self.wss_url = self._current_url()
        self.http_url = (
            self.wss_url.replace("wss://", "https://").rstrip("/")
            if self.wss_url
            else ""
        )
        log.info(
            "Switched Polygon RPC endpoint",
            previous=previous,
            current=self.wss_url,
        )
        return True

    def _next_id(self) -> int:
        """Generate next JSON-RPC request ID."""
        self._request_id += 1
        return self._request_id

    async def connect(self) -> None:
        """Establish WebSocket connection."""
        if not self.wss_url:
            raise ValueError("POLYGON_WSS_URLS is not configured")

        log.info("Connecting to WebSocket", url=self.wss_url[:50] + "...")
        try:
            # Create SSL context for compatibility
            ssl_context = ssl.create_default_context()

            self._ws = await websockets.connect(
                self.wss_url,
                ping_interval=30,
                ping_timeout=10,
                ssl=ssl_context,
            )
            metrics.polygon_connected.set(1)
            log.info("WebSocket connected")
        except Exception as e:
            log.error("WebSocket connection failed", error=str(e))
            raise

    async def disconnect(self) -> None:
        """Close WebSocket and HTTP connections."""
        if self._ws:
            await self._ws.close()
            self._ws = None
        if self._http_session:
            await self._http_session.close()
            self._http_session = None
        metrics.polygon_connected.set(0)

    async def _get_http_session(self) -> aiohttp.ClientSession:
        """Get or create reusable HTTP session."""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        return self._http_session

    async def _rpc_call(self, method: str, params: list | None = None) -> Any:
        """Make JSON-RPC call over HTTP with retry until success.

        Retries indefinitely until the RPC response does not contain an error.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or [],
        }

        session = await self._get_http_session()

        rpc_retries = 0
        while True:
            try:
                async with session.post(
                    self.http_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as resp:
                    result = await resp.json()

                    if "error" in result:
                        metrics.rpc_failures_total.labels(method=method).inc()
                        log.warning(
                            "RPC error, retrying",
                            method=method,
                            error=result["error"].get(
                                "message", str(result["error"])
                            ),
                        )
                        await asyncio.sleep(self.RPC_RETRY_DELAY_SECONDS)
                        rpc_retries += 1
                        continue

                    return result["result"]

            except (aiohttp.ClientError, json.JSONDecodeError) as e:
                metrics.rpc_failures_total.labels(method=method).inc()
                log.warning(
                    "RPC request failed, retrying",
                    method=method,
                    error=str(e),
                )
                await asyncio.sleep(self.RPC_RETRY_DELAY_SECONDS)
                if rpc_retries == 0 and len(self._endpoints) > 1:
                    self._advance_endpoint()
                rpc_retries += 1
                continue

    async def subscribe_blocks(
        self, callback: Callable[[int], Awaitable[None]]
    ) -> None:
        """Subscribe to new block headers via WebSocket with automatic failover."""
        subscribe_msg = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "eth_subscribe",
            "params": ["newHeads"],
        }

        while True:
            try:
                if not self._ws:
                    await self.connect()

                await self._ws.send(json.dumps(subscribe_msg))
                await self._ws.recv()  # subscription confirmation

                # Listen for new blocks
                async for message in self._ws:
                    data = json.loads(message)
                    if "params" in data:
                        block_number = int(data["params"]["result"]["number"], 16)
                        await callback(block_number)
            except (
                websockets.exceptions.ConnectionClosed,
                ConnectionError,
                OSError,
            ) as e:
                log.warning(
                    "WebSocket error, switching endpoint",
                    error=str(e),
                )
                await self.disconnect()
                if not self._advance_endpoint():
                    raise
                continue
            except Exception as e:
                log.error("Unexpected WebSocket error", error=str(e))
                await self.disconnect()
                raise

    async def get_block_with_transactions(self, block_number: int) -> dict:
        """Fetch full block with all transactions."""
        hex_block = hex(block_number)
        return await self._rpc_call("eth_getBlockByNumber", [hex_block, True])

    async def get_transaction_receipt(self, tx_hash: str) -> Optional[dict]:
        """Fetch transaction receipt."""
        return await self._rpc_call("eth_getTransactionReceipt", [tx_hash])

    async def get_block_receipts(self, block_number: int) -> list[dict]:
        """Fetch all transaction receipts for a block in one call."""
        hex_block = hex(block_number)
        result = await self._rpc_call("eth_getBlockReceipts", [hex_block])
        return result or []
