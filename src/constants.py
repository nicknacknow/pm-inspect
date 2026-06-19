"""Application constants."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

# Load environment variables from .env in project root
load_dotenv(PROJECT_ROOT / ".env")

# Polygon WebSocket endpoint - configurable via POLYGON_WSS_URL env var
POLYGON_WSS_URL = os.getenv("POLYGON_WSS_URL")
POLYGON_WSS_URL_SECONDARY = os.getenv("POLYGON_WSS_URL_SECONDARY", "").strip() or None

# Redis Pub/Sub settings
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0").strip()

# Prometheus metrics endpoint
METRICS_PORT = int(os.getenv("METRICS_PORT", "8001"))
