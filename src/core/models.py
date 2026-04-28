"""Data models for trade monitoring."""
from dataclasses import dataclass


@dataclass
class DecodedOrder:
    """Represents a decoded order from the blockchain transaction."""

    salt: int
    maker: str
    signer: str
    token_id: str
    maker_amount: int
    taker_amount: int
    side: int  # 0 = BUY, 1 = SELL
    signature_type: int
    timestamp: int  # order creation time in milliseconds
    metadata: bytes
    builder: bytes
    signature: bytes


@dataclass
class DecodedTransaction:
    condition_id: str
    orders: list[DecodedOrder]


@dataclass
class TradeData:
    """Trade data emitted when a matching transaction is found."""

    block_number: int
    timestamp: str  # ISO 8601 UTC timestamp from block
    transaction_hash: str
    wallet: str  # The wallet address that made the trade
    token_id: str
    condition_id: str
    side: int  # 0 = BUY, 1 = SELL
    maker_amount: int
    taker_amount: int