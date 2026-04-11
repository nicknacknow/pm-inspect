# pminspect

`pminspect` is a focused publisher service: it listens to Polygon blocks for Polymarket trades and publishes each trade as a Redis Pub/Sub event.

## What this repo contains

- Publisher CLI (`pminspect listen`)
- Trade event schema helpers
- `src/pubsub/` module for topic constants, local schema loading, and publish-time payload validation
- A standalone `src/template_listener.py` you can copy into a separate listener repo (no `src.*` imports)

## Setup

```bash
uv venv --python 3.12
source .venv/bin/activate
git submodule update --init --recursive
uv pip install -e .
```

## Configuration

Copy `.env.example` to `.env` and set values:

```bash
cp .env.example .env
```

```env
POLYGON_WSS_URL=wss://your-polygon-wss-endpoint
REDIS_URL=redis://localhost:6379/0
```

## Run Redis

`pminspect` expects Redis to be available before startup.

### Option 1: Docker (recommended)

```bash
docker run --name pminspect-redis -p 6379:6379 -d redis:7-alpine
docker exec -it pminspect-redis redis-cli ping
# PONG
```

### Option 2: Ubuntu/WSL

```bash
sudo apt update
sudo apt install -y redis-server
redis-server --daemonize yes
redis-cli ping
# PONG
```

## Publisher usage

```bash
pminspect [OPTIONS]
```

Options:

| Option | Short | Description |
|---|---|---|
| `--redis-url TEXT` |  | Redis URL |

## Template listener usage

The template listener is intentionally standalone: hardcoded config, local formatting logic, and no imports from this service package.

```bash
python src/template_listener.py
```

Edit `REDIS_URL`, `CHANNEL`, and `MIN_USDC` at the top of the file.

## Event shape

`pminspect` validates events against schema-platform submodule contract at:

`external/pm-event-schema-platform/schemas/polymarket/trade/v1.0.0/schema.json`

Each published message is JSON:

```json
{
  "event_type": "trade",
  "event_version": "1.0.0",
  "trade": {
    "block_number": 0,
    "timestamp": "2026-01-01T00:00:00+00:00",
    "transaction_hash": "0x...",
    "wallet": "0x...",
    "token_id": "123",
    "side": 0,
    "maker_amount": 1000000,
    "taker_amount": 2000000
  }
}
```

## Tests: possible and worth doing?

Yes. This repo now has deterministic event payload logic and a focused publisher pipeline, so unit tests are straightforward and high-value.

Recommended first tests:

1. event serialization/deserialization round-trip
2. monitor callback wiring (mock publisher client)
3. publisher transport behavior (mock Redis publish call)

## TODO

1. Add monitor callback wiring tests (mock publisher + monitor stream).
2. Add publisher transport behavior tests (mock Redis publish failure/success).
