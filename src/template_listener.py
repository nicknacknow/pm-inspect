"""Standalone template listener for pminspect trade events."""

import asyncio
import json

import redis.asyncio as redis

# Hardcoded config for quick copy/paste into a separate repo.
REDIS_URL = "redis://localhost:6379/0"
CHANNEL = "trades.raw"
MIN_USDC = 0.0


def format_trade(trade: dict) -> dict:
    """Mirror pminspect formatter output from raw trade payload."""
    side = int(trade["side"])
    maker_amount = int(trade["maker_amount"])
    taker_amount = int(trade["taker_amount"])

    is_buy = side == 0
    if is_buy:
        usdc = maker_amount / 1_000_000
        tokens = taker_amount / 1_000_000
    else:
        usdc = taker_amount / 1_000_000
        tokens = maker_amount / 1_000_000

    price = usdc / tokens if tokens > 0 else 0.0
    return {
        "wallet": str(trade["wallet"]),
        "token_id": str(trade["token_id"]),
        "side": "BUY" if is_buy else "SELL",
        "tokens": tokens,
        "price": price,
        "total_usdc": usdc,
        "tx_hash": str(trade["transaction_hash"]),
        "block_number": int(trade["block_number"]),
        "timestamp": str(trade["timestamp"]),
    }


def print_trade(formatted: dict) -> None:
    """Simple stdout output; customize this in your listener repo."""
    print(
        f"[{formatted['timestamp']}] "
        f"{formatted['side']} "
        f"${formatted['total_usdc']:.2f} "
        f"tokens={formatted['tokens']:.3f} "
        f"price=${formatted['price']:.4f} "
        f"wallet={formatted['wallet'][:10]}... "
        f"tx={formatted['tx_hash'][:10]}..."
    )


async def main() -> None:
    """Subscribe to Redis trade events and print formatted trades."""
    client = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe(CHANNEL)
    print(f"listening on {CHANNEL} via {REDIS_URL}")

    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            raw_data = message.get("data")
            if not isinstance(raw_data, str):
                continue

            try:
                payload = json.loads(raw_data)
                trade = payload["trade"]
                formatted = format_trade(trade)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue

            if formatted["total_usdc"] < MIN_USDC:
                continue

            print_trade(formatted)
    finally:
        await pubsub.unsubscribe(CHANNEL)
        await pubsub.aclose()
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())

