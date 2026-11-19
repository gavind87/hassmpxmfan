"""Shared base for the read-only monitoring entities (sensor/binary_sensor).

These entities all share one coordinator per fan (see `coordinator.py`) and
read a single named attribute off whatever `DeviceStatus` object the
coordinator last fetched, instead of each polling the device independently.
"""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import XiaomiMiioFanDataUpdateCoordinator


class XiaomiMiioFanMonitoringEntity(
    CoordinatorEntity[XiaomiMiioFanDataUpdateCoordinator]
):
    """Base class for a single read-only attribute of a fan's status."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: XiaomiMiioFanDataUpdateCoordinator,
        *,
        device_name: str,
        model: str,
        device_unique_id: str,
        sw_version: str | None,
        raw_attribute: str,
        unique_id_suffix: str,
        name: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._raw_attribute = raw_attribute
        self._attr_name = name
        self._attr_unique_id = f"{device_unique_id}-{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_unique_id)},
            name=device_name,
            manufacturer="Xiaomi",
            model=model,
            sw_version=sw_version,
        )

    @property
    def _raw_value(self):
        """Return the current raw value for this entity's attribute, if any."""
        state = self.coordinator.data
        if state is None:
            return None
        return getattr(state, self._raw_attribute, None)

    @property
    def available(self) -> bool:
        """Return True if the coordinator is healthy and the value is known."""
        return self.coordinator.last_update_success and self._raw_value is not None
