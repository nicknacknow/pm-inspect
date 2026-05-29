"""Block processing for trade extraction."""
import asyncio
from datetime import datetime, timezone
from time import perf_counter
from typing import Optional

from src.api.polygon import PolygonClient
from src.core.abi import CTF_MATCH_ORDERS_SELECTOR, NEGRISK_MATCH_ORDERS_SELECTOR
from src.core.decoder import TransactionDecoder
from src.core.models import TradeData
from src.core.wallet_filter import WalletFilter
from src.metrics import metrics
from src.utils.logging import get_logger

log = get_logger(__name__)

# Known Polymarket contract addresses (https://docs.polymarket.com/resources/contracts)
POLYMARKET_CONTRACTS = {
    "0xE111180000d2663C0091e4f400237545B87B996B",  # CTF Exchange v2
    "0xe2222d279d744050d28e00520010520000310F59",  # NegRisk CTF Exchange v2
    "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",  # NegRisk Operator v2
}

# Lowercase all contract addresses once so membership checks with tx_to.lower() are reliable
POLYMARKET_CONTRACTS = {addr.lower() for addr in POLYMARKET_CONTRACTS}

class BlockProcessor:
    """Processes blocks and extracts matching trades."""

    def __init__(
        self,
        client: PolygonClient,
        decoder: TransactionDecoder,
        wallet_filter: WalletFilter,
    ) -> None:
        self.client = client
        self.decoder = decoder
        self.filter = wallet_filter

    async def process_block(self, block_number: int) -> list[TradeData]:
        """Process all transactions in a block."""
        started_at = perf_counter()
        trades = []
        try:
            block = None
            for _ in range(3):
                block = await self.client.get_block_with_transactions(block_number)
                if block:
                    break
                await asyncio.sleep(0.25)

            if not block:
                log.warning("Block not available yet", block=block_number)
                return []

            receipts = await self.client.get_block_receipts(block_number)

            # Extract block timestamp (hex Unix epoch → ISO 8601)
            block_ts_hex = block.get("timestamp")
            if not block_ts_hex:
                log.warning("Block missing timestamp", block=block_number)
                return []
            block_ts = int(block_ts_hex, 16)
            timestamp = datetime.fromtimestamp(block_ts, tz=timezone.utc).isoformat()

            # Build receipt lookup by tx hash, skipping null/malformed receipts
            receipt_map: dict[str, dict] = {}
            for r in receipts:
                if not isinstance(r, dict):
                    continue
                tx_hash = r.get("transactionHash")
                if tx_hash:
                    receipt_map[tx_hash] = r

            transactions = block.get("transactions") or []
            log.info("Processing block", block=block_number, txs=len(transactions))
            metrics.transactions_scanned_total.inc(len(transactions))

            # Debug: check for Polymarket transactions
            ctf_selector = "0x" + CTF_MATCH_ORDERS_SELECTOR.hex()
            negrisk_selector = "0x" + NEGRISK_MATCH_ORDERS_SELECTOR.hex()

            for tx in transactions:
                if not isinstance(tx, dict):
                    continue

                tx_input = tx.get("input", "")
                tx_to = (tx.get("to") or "").lower()

                # Check if this is a Polymarket contract
                if tx_to in POLYMARKET_CONTRACTS:
                    selector = tx_input[:10] if len(tx_input) >= 10 else "none"
                    log.info(
                        "Found Polymarket contract tx",
                        to=tx_to[:10],
                        selector=selector,
                        matches_ctf=(selector == ctf_selector),
                        matches_negrisk=(selector == negrisk_selector),
                    )

                tx_hash = tx.get("hash")
                if not tx_hash:
                    continue

                receipt = receipt_map.get(tx_hash)
                trade = self._process_transaction(tx, block_number, timestamp, receipt)
                if trade:
                    trades.append(trade)

            metrics.blocks_processed_total.inc()
            metrics.latest_block_number.set(block_number)
            metrics.trades_detected_total.inc(len(trades))
            return trades
        finally:
            metrics.block_processing_seconds.observe(perf_counter() - started_at)

    def _process_transaction(
        self, tx: dict, block_number: int, timestamp: str, receipt: Optional[dict]
    ) -> Optional[TradeData]:
        """Process single transaction and return TradeData if matching."""
        tx_input = tx.get("input") or ""
        result = self.decoder.decode(tx_input)
        if not result:
            return None

        matching_order = self.filter.filter(result.orders, receipt)
        if not matching_order:
            return None

        tx_hash = tx.get("hash")
        if not tx_hash:
            return None

        return TradeData(
            block_number=block_number,
            timestamp=timestamp,
            transaction_hash=tx_hash,
            wallet=matching_order.maker,
            token_id=matching_order.token_id,
            condition_id=result.condition_id,
            side=matching_order.side,
            maker_amount=matching_order.maker_amount,
            taker_amount=matching_order.taker_amount,
        )
