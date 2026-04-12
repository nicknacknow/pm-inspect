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

# Redis Pub/Sub settings
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0").strip()
