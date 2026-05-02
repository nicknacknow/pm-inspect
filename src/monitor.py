"""Real-time trade monitor via WebSocket."""

import asyncio
from typing import Any, Callable, Optional

from src.api.polygon import PolygonClient
from src.core.block_processor import BlockProcessor
from src.core.decoder import TransactionDecoder
from src.core.wallet_filter import WalletFilter
from src.utils.logging import get_logger

log = get_logger(__name__)


class TradeMonitor:
    """Main orchestrator for monitoring wallet trades."""

    def __init__(self, wss_url: Optional[str] = None) -> None:
        self.client = PolygonClient(wss_url) if wss_url else PolygonClient()
        self.decoder = TransactionDecoder()
        self._callbacks: dict[str, list[Callable]] = {
            "transaction": [],
            "error": [],
            "close": [],
        }
        self._running = False
        self._last_block_number: int | None = None

    def on(self, event: str, callback: Callable) -> None:
        """Register event callback."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def emit(self, event: str, data: Any) -> None:
        """Emit event to all registered callbacks."""
        for callback in self._callbacks.get(event, []):
            if asyncio.iscoroutinefunction(callback):
                asyncio.create_task(callback(data))
            else:
                callback(data)

    async def start(self, target_wallets: list[str]) -> None:
        """Start monitoring for trades from target wallets."""
        self._running = True
        wallet_count = len(target_wallets) if target_wallets else 0
        log.info("Starting monitor", wallet_count=wallet_count)

        wallet_filter = WalletFilter(target_wallets)
        processor = BlockProcessor(self.client, self.decoder, wallet_filter)

        if wallet_filter.is_tracking_all:
            log.info("Tracking ALL Polymarket trades")
        else:
            log.info("Tracking specific wallets", count=wallet_count)

        try:
            while self._running:
                error: Exception | None = None

                try:
                    await self.client.connect()
                    await self.client.subscribe_blocks(
                        lambda block_num: self._on_block(block_num, processor),
                        last_processed_block=self._last_block_number,
                    )
                except asyncio.CancelledError:
                    raise
                except ValueError:
                    raise
                except Exception as e:
                    error = e

                if not self._running:
                    break

                if error is None:
                    log.warning("Connection closed", details={"code": -1, "reason": "subscription ended"})
                    self.emit("close", {"code": -1, "reason": "subscription ended"})
                else:
                    log.error("Monitor error", error=str(error))
                    self.emit("error", error)
                    self.emit("close", {"code": -1, "reason": str(error)})

                await self.client.disconnect()

                await asyncio.sleep(self.client.RECONNECT_DELAY_SECONDS)
        finally:
            self._running = False
            await self.client.disconnect()

    async def _on_block(self, block_number: int, processor: BlockProcessor) -> None:
        """Handle new block event."""
        try:
            trades = await processor.process_block(block_number)
            self._last_block_number = block_number
            for trade in trades:
                self.emit("transaction", trade)
        except Exception as e:
            log.error("Block processing error", block=block_number, error=str(e))
            self.emit("error", e)

    async def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        await self.client.disconnect()
        log.info("Monitor stopped")
