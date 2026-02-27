"""Stub for homeassistant.helpers.config_validation."""

import voluptuous as vol


def entity_id(value: str) -> str:
    """Validate that value is a valid entity ID (domain.object_id)."""
    if not isinstance(value, str):
        raise vol.Invalid("Entity ID must be a string")
    parts = value.split(".")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise vol.Invalid(f"Invalid entity ID: {value!r}")
    return value
