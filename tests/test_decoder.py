"""Tests for transaction decoding."""

import unittest
from unittest.mock import patch

from src.core.abi import MATCH_ORDERS_ABI_TYPES, MATCH_ORDERS_SELECTOR
from src.core.decoder import TransactionDecoder
from src.core.models import DecodedOrder


def make_order_tuple(
    maker: str = "0xaabbccddeeff00112233445566778899aabbccdd",
) -> tuple:
    return (
        1,
        maker,
        "0x1111111111111111111111111111111111111111",
        "0x2222222222222222222222222222222222222222",
        123,
        1_000_000,
        2_000_000,
        1234567890,
        7,
        25,
        1,
        1,
        b"signature",
    )


class TransactionDecoderTests(unittest.TestCase):
    def test_decode_returns_none_for_non_match_orders_input(self) -> None:
        decoder = TransactionDecoder()

        self.assertIsNone(decoder.decode("0x1234"))
        self.assertIsNone(decoder.decode("0xdeadbeef00000000"))

    @patch("src.core.decoder.decode")
    def test_decode_parses_taker_and_maker_orders(self, abi_decode) -> None:
        decoder = TransactionDecoder()
        taker_order = make_order_tuple()
        maker_order = make_order_tuple(maker="0x3333333333333333333333333333333333333333")
        abi_decode.return_value = (taker_order, [maker_order], 0, 0, [], 0, [])

        tx_input = "0x" + MATCH_ORDERS_SELECTOR.hex() + "deadbeef"
        orders = decoder.decode(tx_input)

        self.assertEqual(len(orders or []), 2)
        self.assertEqual(
            orders,
            [
                DecodedOrder(
                    salt=1,
                    maker=taker_order[1],
                    signer=taker_order[2],
                    taker=taker_order[3],
                    token_id="123",
                    maker_amount=1_000_000,
                    taker_amount=2_000_000,
                    expiration=1234567890,
                    nonce=7,
                    fee_rate_bps=25,
                    side=1,
                    signature_type=1,
                    signature=b"signature",
                ),
                DecodedOrder(
                    salt=1,
                    maker=maker_order[1],
                    signer=maker_order[2],
                    taker=maker_order[3],
                    token_id="123",
                    maker_amount=1_000_000,
                    taker_amount=2_000_000,
                    expiration=1234567890,
                    nonce=7,
                    fee_rate_bps=25,
                    side=1,
                    signature_type=1,
                    signature=b"signature",
                ),
            ],
        )
        abi_decode.assert_called_once_with(MATCH_ORDERS_ABI_TYPES, bytes.fromhex("deadbeef"))


if __name__ == "__main__":
    unittest.main()
