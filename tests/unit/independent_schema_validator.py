"""Independent minimal JSON Schema validator (P032 T009).

This module is the *independent* check on ``accepttwin.report/v1``:
it reads only the Schema file
(``schemas/accepttwin.report.v1.schema.json``) and validates plain
JSON data against it, using only the Python standard library. It
deliberately does **not** import ``accepttwin.report_builder`` (or
any other production module): a report that passes here passed a
checker that shares no code with the generator, so the generator
cannot validate itself into a PASS.

Supported keywords (the subset the report Schema uses): ``$ref``
(local ``#/$defs/...`` only), ``$defs``, ``type`` (string or list),
``const``, ``enum``, ``required``, ``properties``,
``additionalProperties`` (boolean or schema), ``pattern`` (ECMA-style
regular expression, applied with search semantics as JSON Schema
specifies), ``minimum``, ``maximum``, ``minLength``, ``items``, ``minItems``,
``maxItems``, ``propertyNames``. Anything else in the Schema is
ignored by this validator — if the Schema ever gains a keyword
this module does not understand, validation silently weakens, so
``test_report_schema.py`` asserts the Schema uses only these
keywords.

Limitations, stated plainly: this is a *minimal* validator, not a
full JSON Schema implementation. It does not implement ``format``,
``allOf``/``anyOf``/``oneOf``/``not`` (other than inside
``propertyNames`` via ``pattern``), ``$dynamicRef``, remote ``$ref``,
or numeric ``multipleOf``/``exclusiveMinimum``. The report Schema
is written to stay inside the supported subset.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

__all__ = ["SchemaError", "load_schema", "validate", "validate_report_file"]

#: Keywords this validator understands. Anything else in the Schema
#: is ignored — see the module docstring.
SUPPORTED_KEYWORDS: frozenset[str] = frozenset(
    {
        "$defs",
        "$ref",
        "additionalProperties",
        "const",
        "enum",
        "items",
        "maxItems",
        "maximum",
        "minItems",
        "minLength",
        "minimum",
        "pattern",
        "properties",
        "propertyNames",
        "required",
        "type",
    }
)

_DEFAULT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "schemas"
    / "accepttwin.report.v1.schema.json"
)


class SchemaError(ValueError):
    """Raised when the Schema file itself cannot be loaded."""


def load_schema(path: str | Path | None = None) -> dict[str, Any]:
    """Read and return the report Schema as plain JSON data."""
    schema_path = Path(path) if path is not None else _DEFAULT_SCHEMA_PATH
    try:
        data = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SchemaError(
            f"cannot load report schema {schema_path}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise SchemaError(f"report schema {schema_path} must be a JSON object")
    return data


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (isinstance(value, (int, float)) and not isinstance(value, bool))
    if expected == "null":
        return value is None
    return False


def _resolve(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    """Resolve a local ``#/...`` reference against the Schema root."""
    if not ref.startswith("#/"):
        raise SchemaError(f"only local refs are supported, got {ref!r}")
    node: Any = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            raise SchemaError(f"unresolvable ref {ref!r}")
        node = node[part]
    if not isinstance(node, dict):
        raise SchemaError(f"ref {ref!r} does not point at a schema object")
    return node


def _validate(
    instance: Any, schema: dict[str, Any], root: dict[str, Any], path: str
) -> list[str]:
    """Return the list of validation errors for *instance* at *path*."""
    errors: list[str] = []
    if "$ref" in schema:
        errors.extend(_validate(instance, _resolve(schema["$ref"], root), root, path))
        return errors
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: must be {schema['const']!r}, got {instance!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: must be one of {schema['enum']!r}, got {instance!r}")
    expected_type = schema.get("type")
    if expected_type is not None:
        types = [expected_type] if isinstance(expected_type, str) else expected_type
        if not any(_type_matches(instance, t) for t in types):
            errors.append(
                f"{path}: must be of type {types!r}, got {type(instance).__name__} ({instance!r})"
            )
            return errors  # further keyword checks assume the type
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(
                f"{path}: string is too short (minimum {schema['minLength']})"
            )
        if "pattern" in schema:
            try:
                if re.search(schema["pattern"], instance) is None:
                    errors.append(
                        f"{path}: {instance!r} does not match pattern {schema['pattern']!r}"
                    )
            except re.error as exc:
                errors.append(f"{path}: invalid pattern {schema['pattern']!r}: {exc}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance!r} is less than minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance!r} is greater than maximum {schema['maximum']}")
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        for key, value in instance.items():
            child_path = f"{path}.{key}"
            if key in properties:
                errors.extend(
                    _validate(value, properties[key], root, child_path)
                )
            elif "additionalProperties" in schema:
                extra = schema["additionalProperties"]
                if extra is False:
                    errors.append(f"{path}: additional property {key!r} is not allowed")
                elif isinstance(extra, dict):
                    errors.extend(_validate(value, extra, root, child_path))
        if "propertyNames" in schema:
            name_schema = schema["propertyNames"]
            for key in instance:
                name_errors = _validate(key, name_schema, root, f"{path} (property name)")
                errors.extend(name_errors)
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(
                f"{path}: array has {len(instance)} items, minimum {schema['minItems']}"
            )
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(
                f"{path}: array has {len(instance)} items, maximum {schema['maxItems']}"
            )
        if "items" in schema:
            for index, item in enumerate(instance):
                errors.extend(
                    _validate(item, schema["items"], root, f"{path}[{index}]")
                )
    return errors


def validate(
    instance: Any, schema: dict[str, Any] | None = None
) -> list[str]:
    """Validate *instance* against the report Schema.

    Returns the list of error strings (empty means valid). *schema*
    defaults to the Schema file on disk; pass an explicit parsed
    schema only in validator self-tests.
    """
    root = schema if schema is not None else load_schema()
    if not isinstance(root, dict):
        raise SchemaError("schema must be a JSON object")
    return _validate(instance, root, root, "$")


def validate_report_file(path: str | Path) -> list[str]:
    """Validate the JSON report file at *path*; return error strings."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"{path}: cannot read report JSON: {exc}"]
    return validate(data)
