"""Tests for Prometheus metrics wiring."""

import unittest
from unittest.mock import patch

from prometheus_client import generate_latest

from src.metrics import ServiceMetrics


class ServiceMetricsTests(unittest.TestCase):
    @patch("src.metrics.start_http_server")
    def test_serve_exposes_registry_once(self, start_http_server_mock) -> None:
        metrics = ServiceMetrics()

        metrics.serve(9000)
        metrics.serve(9000)

        start_http_server_mock.assert_called_once_with(9000, registry=metrics.registry)

    def test_registry_exports_core_metrics(self) -> None:
        metrics = ServiceMetrics()

        metrics.monitor_running.set(1)
        metrics.polygon_connected.set(1)
        metrics.redis_connected.set(0)
        metrics.latest_block_number.set(123)
        metrics.blocks_processed_total.inc()
        metrics.transactions_scanned_total.inc(4)
        metrics.trades_detected_total.inc(2)
        metrics.trades_published_total.inc()
        metrics.trade_publish_failures_total.inc()
        metrics.monitor_errors_total.inc()
        metrics.block_errors_total.inc()
        metrics.trade_event_validation_failures_total.inc()
        metrics.transaction_decode_errors_total.inc()
        metrics.rpc_failures_total.labels(method="eth_getBlockByNumber").inc()
        metrics.block_processing_seconds.observe(0.25)
        metrics.trade_publish_seconds.observe(0.05)

        exported = generate_latest(metrics.registry).decode()

        self.assertIn("pminspect_blocks_processed_total 1.0", exported)
        self.assertIn("pminspect_latest_block_number 123.0", exported)
        self.assertIn(
            'pminspect_rpc_failures_total{method="eth_getBlockByNumber"} 1.0',
            exported,
        )


if __name__ == "__main__":
    unittest.main()