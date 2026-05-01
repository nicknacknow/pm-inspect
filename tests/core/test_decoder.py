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
        123,
        1_000_000,
        2_000_000,
        1,
        1,
        1234567890,
        bytes.fromhex("00" * 32),
        bytes.fromhex("11" * 32),
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
        condition_id = bytes.fromhex("11" * 32)
        abi_decode.return_value = (condition_id, taker_order, [maker_order], 0, [], 0, [])

        tx_input = "0x" + MATCH_ORDERS_SELECTOR.hex() + "deadbeef"
        decoded = decoder.decode(tx_input)

        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.condition_id, "0x" + condition_id.hex())
        self.assertEqual(
            decoded.orders,
            [
                DecodedOrder(
                    salt=1,
                    maker=taker_order[1],
                    signer=taker_order[2],
                    token_id="123",
                    maker_amount=1_000_000,
                    taker_amount=2_000_000,
                    side=1,
                    signature_type=1,
                    timestamp=1234567890,
                    metadata=bytes.fromhex("00" * 32),
                    builder=bytes.fromhex("11" * 32),
                    signature=b"signature",
                ),
                DecodedOrder(
                    salt=1,
                    maker=maker_order[1],
                    signer=maker_order[2],
                    token_id="123",
                    maker_amount=1_000_000,
                    taker_amount=2_000_000,
                    side=1,
                    signature_type=1,
                    timestamp=1234567890,
                    metadata=bytes.fromhex("00" * 32),
                    builder=bytes.fromhex("11" * 32),
                    signature=b"signature",
                ),
            ],
        )
        abi_decode.assert_called_once_with(MATCH_ORDERS_ABI_TYPES, bytes.fromhex("deadbeef"))


if __name__ == "__main__":
    unittest.main()
