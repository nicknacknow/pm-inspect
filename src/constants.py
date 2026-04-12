"""Application constants."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

# Load environment variables from .env in project root
load_dotenv(PROJECT_ROOT / ".env")

# Polygon WebSocket endpoint - configurable via POLYGON_WSS_URL env var
POLYGON_WSS_URL = os.getenv("POLYGON_WSS_URL", "").strip()


def get_polygon_wss_url() -> str:
    """Return the configured Polygon WSS URL or raise a clear error."""
    if not POLYGON_WSS_URL:
        raise RuntimeError(
            "POLYGON_WSS_URL is not set. Add it to .env or your environment."
        )
    return POLYGON_WSS_URL

# Redis Pub/Sub settings
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0").strip()
