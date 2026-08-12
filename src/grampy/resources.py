from __future__ import annotations

from importlib.resources import files
import json
from typing import Any


def load_json(directory: str, name: str) -> dict[str, Any]:
    resource = files("grampy").joinpath(directory, name)
    value = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"package resource must contain a JSON object: {directory}/{name}")
    return value
