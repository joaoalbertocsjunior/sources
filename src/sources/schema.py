"""JSON schema validation utilities. jsonschema is optional — degrades gracefully."""
from __future__ import annotations

from typing import Any


class SchemaError(Exception):
    """JSON schema validation failure."""


def validate_schema(data: Any, schema: dict[str, Any]) -> None:
    """Validate *data* against *schema*. Raises SchemaError on failure.

    Uses jsonschema if available; falls back to basic type/required checks.
    Install extras: pip install sources-lib[validation]
    """
    if not schema:
        return
    try:
        import jsonschema
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as exc:
            raise SchemaError(str(exc.message)) from exc
    except ImportError:
        _basic_validate(data, schema)


def _basic_validate(data: Any, schema: dict[str, Any]) -> None:
    """Minimal validation without jsonschema: required fields + type checks."""
    if not isinstance(data, dict):
        raise SchemaError(f"Expected object, got {type(data).__name__}")
    for field in schema.get("required", []):
        if field not in data:
            raise SchemaError(f"Required field '{field}' is missing")
    props = schema.get("properties", {})
    for key, prop_schema in props.items():
        if key not in data:
            continue
        expected = prop_schema.get("type")
        if expected is None:
            continue
        type_map = {
            "string": str, "integer": int, "number": (int, float),
            "boolean": bool, "array": list, "object": dict,
        }
        expected_type = type_map.get(expected)
        if expected_type and not isinstance(data[key], expected_type):
            raise SchemaError(
                f"Field '{key}' expected {expected}, got {type(data[key]).__name__}"
            )
