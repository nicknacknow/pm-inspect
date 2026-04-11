"""Load pub/sub schemas from schema-platform submodule."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_SCHEMA_DIR = (
    Path(__file__).resolve().parents[2]
    / "external"
    / "pm-event-schema-platform"
    / "schemas"
)


@lru_cache(maxsize=32)
def load_schema(relative_path: str) -> dict[str, Any]:
    """Load a schema file from external schema-platform submodule."""
    schema_path = _SCHEMA_DIR / relative_path
    if not schema_path.exists():
        raise FileNotFoundError(
            f"schema not found at {schema_path}. "
            "Run: git submodule update --init --recursive"
        )
    with schema_path.open(encoding="utf-8") as f:
        return json.load(f)

