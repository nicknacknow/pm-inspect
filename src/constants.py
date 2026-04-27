"""Application constants."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

# Load environment variables from .env in project root
load_dotenv(PROJECT_ROOT / ".env")

# Polygon WebSocket endpoints - configurable via POLYGON_WSS_URLS or POLYGON_WSS_URL env vars
def _parse_env_urls(raw_value: str | None) -> tuple[str, ...]:
    if not raw_value:
        return ()

    urls = []
    for part in raw_value.replace("\n", ",").split(","):
        url = part.strip()
        if url:
            urls.append(url)
    return tuple(urls)


POLYGON_WSS_URLS = _parse_env_urls(os.getenv("POLYGON_WSS_URLS"))
POLYGON_WSS_URL = os.getenv("POLYGON_WSS_URL")

# Redis Pub/Sub settings
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0").strip()
