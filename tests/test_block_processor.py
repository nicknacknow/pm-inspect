"""Tests for block processing orchestration."""

import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

from src.core.block_processor import BlockProcessor
from src.core.models import DecodedOrder, TradeData


def make_order() -> DecodedOrder:
    return DecodedOrder(
        salt=1,
        maker="0xaabbccddeeff00112233445566778899aabbccdd",
        signer="0x1111111111111111111111111111111111111111",
        taker="0x2222222222222222222222222222222222222222",
        token_id="123",
        maker_amount=1_000_000,
        taker_amount=2_000_000,
        expiration=1234567890,
        nonce=7,
        fee_rate_bps=25,
        side=1,
        signature_type=1,
        signature=b"signature",
    )


class BlockProcessorTests(unittest.IsolatedAsyncioTestCase):
    async def test_process_block_maps_matching_transaction_to_trade(self) -> None:
        block_number = 123
        block_ts = 1_700_000_000
        expected_timestamp = datetime.fromtimestamp(block_ts, tz=timezone.utc).isoformat()

        client = AsyncMock()
        client.get_block_with_transactions.return_value = {
            "timestamp": hex(block_ts),
            "transactions": [
                {
                    "hash": "0xaaa",
                    "input": "0xdeadbeef",
                    "to": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                }
            ],
        }
        client.get_block_receipts.return_value = [
            {"transactionHash": "0xaaa", "status": "0x1"}
        ]

        decoder = Mock()
        matching_order = make_order()
        decoder.decode.return_value = [matching_order]

        wallet_filter = Mock()
        wallet_filter.filter.return_value = matching_order

        processor = BlockProcessor(client, decoder, wallet_filter)

        trades = await processor.process_block(block_number)

        self.assertEqual(
            trades,
            [
                TradeData(
                    block_number=block_number,
                    timestamp=expected_timestamp,
                    transaction_hash="0xaaa",
                    wallet=matching_order.maker,
                    token_id=matching_order.token_id,
                    side=matching_order.side,
                    maker_amount=matching_order.maker_amount,
                    taker_amount=matching_order.taker_amount,
                )
            ],
        )
        client.get_block_with_transactions.assert_awaited_once_with(block_number)
        client.get_block_receipts.assert_awaited_once_with(block_number)
        decoder.decode.assert_called_once_with("0xdeadbeef")
        wallet_filter.filter.assert_called_once_with(
            [matching_order], {"transactionHash": "0xaaa", "status": "0x1"}
        )


if __name__ == "__main__":
    unittest.main()
