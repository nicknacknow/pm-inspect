# TODO

## Short / in-flight
- Explore supporting multiple Polygon WSS RPC endpoints for redundancy and provider quota spreading.
- Decide whether the live ingest path should stay single-source or be partitioned by wallet/token/chain segment for real scaling.

## Backlog — revisit when ready
### Redis-backed last-processed head
What: when a block is successfully processed, store `latest_block_number` in Redis. On `pminspect` startup, read that value and resume from there instead of starting fresh.
Why: right now any container restart silently drops the gap — blocks between last run and now are never inspected. Redis-backed head makes restarts safe and prevents missed trades.

### Decode error labels
What: add a label to `transaction_decode_errors_total` showing the failing selector/contract (or similar context).
Why: today it’s just a number going up. With a label you can see *what* is failing (specific ABI selector? new contract?) and act on it instead of guessing.

### Head block lag metric
What: expose `pminspect_lag_blocks` = `polygon_head_block - pminspect_last_processed_block`.
Why: tells you directly how far behind ingestion is. Without it you only notice lag when trades stop arriving in downstream services.

### Simple SLO alert
What: alert if processing gets worse than baseline — e.g., rolling avg block time spikes, or lag crosses N blocks for M consecutive checks.
Why: catches Polygon RPC slowdown or ingestion stalls before they silently drop trades.
Goal: decode any Polygon block given a block number so we can backfill trades or audit old events.
- Input: `pminspect backfill <block>` or `pminspect backfill <start>..<end>` (new CLI subcommand).
- Reuse existing `src/core/block_processor.py` + `src/core/decoder.py` per-block path; add a non-live entrypoint that accepts a block number instead of reading from the WSS monitor.
- Publish decoded trades through the same Redis Pub/Sub pipeline, using the existing schema/validator. Downstream consumers (`pm-trades-db`, etc.) handle them identically to live events.
- Idempotency: deduplicate on `(transaction_hash, log_index)` / `condition_id` so rerunning a range is safe.
- Guardrails / constraints:
  - Respect Polygon RPC rate limits; prefer `eth_getBlockReceipts` + targeted `eth_getLogs` queries.
  - Add a per-block or per-range timeout + retry policy (exponential backoff).
  - Expose a dry-run mode that only counts candidate trades without publishing, to estimate cost before a full backfill.
  - Track backfill progress (current range, last committed block) in Redis or a small state file so it can be resumed after interruption.
- Nice-to-haves: schema-version compatibility check on historic payloads; pluggable RPC so backfill can spread across multiple providers.
