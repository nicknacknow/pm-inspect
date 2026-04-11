"""Load vendored pub/sub schemas."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_SCHEMA_DIR = Path(__file__).parent / "schemas"


@lru_cache(maxsize=32)
def load_schema(relative_path: str) -> dict[str, Any]:
    """Load a schema file from src/pubsub/schemas."""
    schema_path = _SCHEMA_DIR / relative_path
    with schema_path.open(encoding="utf-8") as f:
        return json.load(f)

