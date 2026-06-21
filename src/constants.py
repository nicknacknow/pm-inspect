"""Application constants."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

# Load environment variables from .env in project root
load_dotenv(PROJECT_ROOT / ".env")

# Polygon WebSocket endpoints, comma-separated.
# Falls back to POLYGON_WSS_URL for backwards compatibility.
_raw_urls = os.getenv("POLYGON_WSS_URLS", "") or os.getenv("POLYGON_WSS_URL", "")
POLYGON_WSS_URLS: list[str] = [u.strip() for u in _raw_urls.split(",") if u.strip()]

# Redis Pub/Sub settings
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0").strip()

# Prometheus metrics endpoint
METRICS_PORT = int(os.getenv("METRICS_PORT", "8001"))
