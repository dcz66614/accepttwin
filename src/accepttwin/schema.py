"""JSON Schema for ``accepttwin.contract/v1`` plus a minimal stdlib validator.

Source of truth for the field set: PROJECT_BOOK.md §5.1 (top-level fields),
§5.1.1 (URL rules — semantic checks live in :mod:`accepttwin.url_guard`),
§5.1.2 (per-representation fields and frozen values), §5.1.3 (fixed request
headers) and §5.2 (``cache_behavior`` modes).

Specification gaps (see VERIFY_LOG.md D-04 / D-06 / D-08): the §5.1.2 JSON
and the T002 output list were truncated in page extraction, so the schema
below is built only from the field tables and prose that *were* retrieved.
Where the spec gives no field name, this module documents the choice instead
of inventing a spec claim:

* Nested objects use the same ``snake_case`` naming as the top-level contract
  fields (``contract_id``, ``origin_url``, ``cache_behavior``).
* ``request_headers`` carries the three fixed common headers as
  ``accept_encoding`` / ``user_agent`` / ``accept_language``. ``Accept`` is
  per-representation (``representations.html.accept`` /
  ``representations.markdown.accept``) per §5.1.3 and is NOT a member of
  ``request_headers``.
* ``limits`` sub-fields are not enumerated in the retrieved spec text
  (§5.1 only says "request and body boundaries"; §17.4 fixes the body cap at
  1 MiB and requires a bounded request timeout). The schema therefore allows
  exactly ``max_body_bytes`` (1..1048576) and ``request_timeout_seconds``
  (> 0); both default when absent (see :mod:`accepttwin.contract`).
* ``metadata`` is a free-form object that does not participate in verdicts
  (§5.1); its keys are unrestricted.

This module uses only the standard library: there is no ``jsonschema``
dependency in the frozen stack (§16: stdlib only + pytest).
"""

from __future__ import annotations

CONTRACT_SCHEMA_VERSION = "accepttwin.contract/v1"

CONTRACT_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://accepttwin.local/schemas/accepttwin.contract.v1.schema.json",
    "title": "AcceptTwin contract",
    "type": "object",
    "required": [
        "schema",
        "contract_id",
        "name",
        "url",
        "origin_url",
        "representations",
        "request_headers",
        "cache_behavior",
        "limits",
        "metadata",
    ],
    "additionalProperties": False,
    "properties": {
        "schema": {"const": CONTRACT_SCHEMA_VERSION},
        "contract_id": {"type": "string", "minLength": 1},
        "name": {"type": "string", "minLength": 1},
        "url": {"type": "string", "minLength": 1},
        "origin_url": {"type": "string", "minLength": 1},
        "representations": {
            "type": "object",
            "required": ["html", "markdown"],
            "additionalProperties": False,
            "properties": {
                "html": {"$ref": "#/$defs/representation"},
                "markdown": {"$ref": "#/$defs/representation"},
            },
        },
        "request_headers": {
            "type": "object",
            "required": ["accept_encoding", "user_agent", "accept_language"],
            "additionalProperties": False,
            "properties": {
                "accept_encoding": {"const": "identity"},
                "user_agent": {"const": "AcceptTwin/1.0.0"},
                "accept_language": {"const": "en"},
            },
        },
        "cache_behavior": {
            "type": "object",
            "required": ["mode"],
            "additionalProperties": False,
            "properties": {
                "mode": {"enum": ["variant_by_accept", "no_store"]},
                "vary_accept": {"enum": ["required", "advisory", "not_required"]},
                "max_age_seconds": {"type": ["integer", "null"], "minimum": 0},
            },
        },
        "limits": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "max_body_bytes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 1048576,
                },
                "request_timeout_seconds": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                },
            },
        },
        "metadata": {"type": "object"},
    },
    "$defs": {
        "representation": {
            "type": "object",
            "required": [
                "accept",
                "expected_status",
                "expected_content_type",
                "sentinel",
            ],
            "additionalProperties": False,
            "properties": {
                "accept": {"type": "string", "minLength": 1},
                "expected_status": {"type": "integer"},
                "expected_content_type": {"type": "string", "minLength": 1},
                "sentinel": {"type": "string", "minLength": 1},
            },
        },
    },
}

# Frozen per-representation values from PROJECT_BOOK §5.1.2. These are
# enforced semantically in contract.py (not merely as schema consts) so the
# error messages can name the representation and the expected value.
FROZEN_REPRESENTATIONS: dict[str, dict[str, object]] = {
    "html": {
        "accept": "text/html",
        "expected_status": 200,
        "expected_content_type": "text/html; charset=utf-8",
    },
    "markdown": {
        "accept": "text/markdown",
        "expected_status": 200,
        "expected_content_type": "text/markdown; charset=utf-8",
    },
}


def _type_name(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return type(value).__name__


def _matches_type(value: object, expected: str) -> bool:
    # JSON Schema: "integer" accepts ints but not bools; "number" accepts
    # ints and floats but not bools.
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return _type_name(value) == expected


def _resolve_ref(ref: str, root: dict) -> dict:
    # Only local refs of the form "#/$defs/<name>" (and "#/properties/...")
    # are used by CONTRACT_SCHEMA.
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported $ref: {ref!r}")
    node: object = root
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            raise ValueError(f"unresolvable $ref: {ref!r}")
        node = node[part]
    if not isinstance(node, dict):
        raise ValueError(f"$ref does not point at a schema object: {ref!r}")
    return node


def _validate(
    value: object, schema: dict, root: dict, path: str, errors: list[str]
) -> None:
    if "$ref" in schema:
        _validate(value, _resolve_ref(schema["$ref"], root), root, path, errors)
        return

    schema_type = schema.get("type")
    if schema_type is not None:
        expected = (
            schema_type if isinstance(schema_type, list) else [schema_type]
        )
        if not any(_matches_type(value, t) for t in expected):
            errors.append(
                f"{path or '$'}: expected type "
                f"{'/'.join(expected)}, got {_type_name(value)}"
            )
            return

    if "const" in schema and value != schema["const"]:
        errors.append(
            f"{path or '$'}: expected {schema['const']!r}, got {value!r}"
        )
    if "enum" in schema and value not in schema["enum"]:
        errors.append(
            f"{path or '$'}: expected one of {schema['enum']!r}, got {value!r}"
        )
    if isinstance(value, str):
        if (
            "minLength" in schema
            and len(value) < schema["minLength"]
        ):
            errors.append(
                f"{path or '$'}: string shorter than "
                f"minLength {schema['minLength']}"
            )
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(
                f"{path or '$'}: value {value!r} below minimum "
                f"{schema['minimum']!r}"
            )
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(
                f"{path or '$'}: value {value!r} above maximum "
                f"{schema['maximum']!r}"
            )
        if (
            "exclusiveMinimum" in schema
            and value <= schema["exclusiveMinimum"]
        ):
            errors.append(
                f"{path or '$'}: value {value!r} not above exclusiveMinimum "
                f"{schema['exclusiveMinimum']!r}"
            )
    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path or '$'}: missing required field {key!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(
                        f"{path or '$'}: unsupported field {key!r} "
                        "(unknown fields are never silently ignored)"
                    )
        for key, subschema in properties.items():
            if key in value:
                child_path = f"{path}.{key}" if path else key
                _validate(value[key], subschema, root, child_path, errors)


def validate_with_schema(
    data: object, schema: dict | None = None
) -> list[str]:
    """Validate *data* against the contract schema.

    Returns the list of error strings (empty means valid). This is a
    structural check only; semantic rules (loopback URLs, distinct
    Sentinels, frozen Accept values, mode combinations) are enforced by
    :mod:`accepttwin.contract` on top of it.
    """
    schema = CONTRACT_SCHEMA if schema is None else schema
    errors: list[str] = []
    _validate(data, schema, schema, "", errors)
    return errors
