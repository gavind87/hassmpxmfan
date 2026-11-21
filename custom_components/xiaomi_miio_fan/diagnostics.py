"""Diagnostics support: the standard "Download diagnostics" button.

The token, host, MAC (embedded in the unique_id) and miIO device ID are
redacted so the file is safe to attach to an issue.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant

TO_REDACT = {CONF_HOST, CONF_TOKEN, "unique_id", "device_id", "mac", "title"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    fan_entity = runtime.fan_entity

    return async_redact_data(
        {
            "entry": {
                "title": entry.title,
                "data": dict(entry.data),
                "options": dict(entry.options),
                "unique_id": entry.unique_id,
            },
            "device": {
                "model": runtime.model,
                "sw_version": runtime.sw_version,
                "device_id": runtime.device_id,
                "retries": runtime.retries,
                "preset_modes_override": runtime.preset_modes_override,
            },
            "fan_entity": {
                "class": type(fan_entity).__name__,
                "available": fan_entity.available,
                "is_on": fan_entity.is_on,
                "percentage": fan_entity.percentage,
                "preset_mode": fan_entity.preset_mode,
                "retry_count": fan_entity._retry,
                "attributes": dict(fan_entity.extra_state_attributes or {}),
            },
            "coordinator": {
                "last_update_success": coordinator.last_update_success,
                "last_exception": repr(coordinator.last_exception),
                "status": repr(coordinator.data),
            },
        },
        TO_REDACT,
    )
