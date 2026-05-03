"""Prometheus metrics for pminspect."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, start_http_server
from prometheus_client.registry import CollectorRegistry


class ServiceMetrics:
    """Prometheus metrics collected by the publisher service."""

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry()
        self._server_started = False

        self.monitor_running = Gauge(
            "pminspect_monitor_running",
            "Whether the monitor loop is running.",
            registry=self.registry,
        )
        self.polygon_connected = Gauge(
            "pminspect_polygon_connected",
            "Whether the Polygon WebSocket is connected.",
            registry=self.registry,
        )
        self.redis_connected = Gauge(
            "pminspect_redis_connected",
            "Whether the Redis publisher is connected.",
            registry=self.registry,
        )
        self.latest_block_number = Gauge(
            "pminspect_latest_block_number",
            "Latest successfully processed block number.",
            registry=self.registry,
        )
        self.blocks_processed_total = Counter(
            "pminspect_blocks_processed_total",
            "Total blocks processed by pminspect.",
            registry=self.registry,
        )
        self.transactions_scanned_total = Counter(
            "pminspect_transactions_scanned_total",
            "Total transactions scanned from Polygon blocks.",
            registry=self.registry,
        )
        self.trades_detected_total = Counter(
            "pminspect_trades_detected_total",
            "Total trade records emitted by the block processor.",
            registry=self.registry,
        )
        self.trades_published_total = Counter(
            "pminspect_trades_published_total",
            "Total trade events published to Redis.",
            registry=self.registry,
        )
        self.trade_publish_failures_total = Counter(
            "pminspect_trade_publish_failures_total",
            "Total Redis publish failures.",
            registry=self.registry,
        )
        self.monitor_errors_total = Counter(
            "pminspect_monitor_errors_total",
            "Total monitor loop errors.",
            registry=self.registry,
        )
        self.block_errors_total = Counter(
            "pminspect_block_errors_total",
            "Total block processing errors.",
            registry=self.registry,
        )
        self.trade_event_validation_failures_total = Counter(
            "pminspect_trade_event_validation_failures_total",
            "Total trade payload validation failures.",
            registry=self.registry,
        )
        self.transaction_decode_errors_total = Counter(
            "pminspect_transaction_decode_errors_total",
            "Total ABI decode errors for Polygon transactions.",
            registry=self.registry,
        )
        self.rpc_failures_total = Counter(
            "pminspect_rpc_failures_total",
            "Total Polygon RPC failures.",
            ["method"],
            registry=self.registry,
        )
        self.block_processing_seconds = Histogram(
            "pminspect_block_processing_seconds",
            "Time spent processing Polygon blocks.",
            registry=self.registry,
        )
        self.trade_publish_seconds = Histogram(
            "pminspect_trade_publish_seconds",
            "Time spent publishing trade events to Redis.",
            registry=self.registry,
        )

    def serve(self, port: int) -> None:
        """Expose metrics on an HTTP endpoint once per process."""
        if self._server_started:
            return

        start_http_server(port, registry=self.registry)
        self._server_started = True


metrics = ServiceMetrics()