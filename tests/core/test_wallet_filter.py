"""Tests for wallet filtering logic."""

import unittest

from src.core.models import DecodedOrder
from src.core.wallet_filter import WalletFilter


def make_order(maker: str = "0xaabbccddeeff00112233445566778899aabbccdd") -> DecodedOrder:
    return DecodedOrder(
        salt=1,
        maker=maker,
        signer="0x1111111111111111111111111111111111111111",
        token_id="123",
        maker_amount=1_000_000,
        taker_amount=2_000_000,
        side=0,
        signature_type=1,
        timestamp=1234567890,
        metadata=bytes.fromhex("00" * 32),
        builder=bytes.fromhex("11" * 32),
        signature=b"signature",
    )


class WalletFilterTests(unittest.TestCase):
    def test_tracks_all_wallets_when_no_filter_is_configured(self) -> None:
        wallet_filter = WalletFilter([])
        order = make_order()

        self.assertTrue(wallet_filter.is_tracking_all)
        self.assertIs(wallet_filter.filter([order], {"status": "0x1"}), order)

    def test_matches_wallet_case_insensitively(self) -> None:
        tracked_wallet = "0xaabbccddeeff00112233445566778899aabbccdd"
        wallet_filter = WalletFilter([tracked_wallet.upper()])
        first_order = make_order(maker="0x3333333333333333333333333333333333333333")
        matching_order = make_order(maker=tracked_wallet)

        self.assertIs(
            wallet_filter.filter([first_order, matching_order], {"status": "0x1"}),
            matching_order,
        )

    def test_rejects_failed_or_missing_receipts(self) -> None:
        wallet_filter = WalletFilter(["0xaabbccddeeff00112233445566778899aabbccdd"])
        order = make_order()

        self.assertIsNone(wallet_filter.filter([order], {"status": "0x0"}))
        self.assertIsNone(wallet_filter.filter([order], None))


if __name__ == "__main__":
    unittest.main()
