"""Load pub/sub schemas from packaged resources."""

import json
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

_SCHEMA_ROOT = files(__package__).joinpath("schemas")


@lru_cache(maxsize=32)
def load_schema(relative_path: str) -> dict[str, Any]:
    """Load a schema file from packaged schema resources."""
    schema_path = _SCHEMA_ROOT.joinpath(*Path(relative_path).parts)
    if not schema_path.is_file():
        raise FileNotFoundError(
            f"schema not found at packaged resource {schema_path}. "
            "Update the packaged schema copy from the schema submodule."
        )
    with schema_path.open(encoding="utf-8") as f:
        return json.load(f)

