"""
JSON Schema validation for canonical_docs.yaml.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError


SCHEMA_PATH = Path(__file__).parent / "canonical_docs.schema.json"
SCHEMA_ID = "c021.canonical_docs.v1"


class ManifestError(ValueError):
    """canonical_docs.yaml failed schema or structural validation."""


def load_schema() -> dict[str, Any]:
    """Load the packaged Draft 2020-12 schema."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as handle:
        schema = json.load(handle)
    if not isinstance(schema, dict):
        raise ManifestError("canonical_docs schema file is not an object")
    return schema


def validate_canonical_docs(data: Any) -> None:
    """
    Validate a loaded canonical-docs mapping against the packaged schema.

    Raises ManifestError on any failure. Does not read repository files.
    """
    if not isinstance(data, dict):
        raise ManifestError("canonical_docs manifest must be a mapping")

    schema = load_schema()
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda err: list(err.path))
    if not errors:
        return

    lines = []
    for err in errors:
        path = "/".join(str(part) for part in err.absolute_path) or "<root>"
        lines.append(f"{path}: {err.message}")
    raise ManifestError(
        "canonical_docs schema validation failed:\n" + "\n".join(lines)
    ) from (errors[0] if isinstance(errors[0], JsonSchemaValidationError) else None)
