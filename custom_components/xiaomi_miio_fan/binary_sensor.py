"""Binary sensor platform for the Xiaomi Mi Smart Pedestal Fan integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import XiaomiMiioFanDataUpdateCoordinator
from .entity import XiaomiMiioFanMonitoringEntity
from .fan import (
    ATTR_AC_POWER,
    ATTR_ERROR_DETECTED,
    ATTR_WATER_TANK_EMPTY,
    get_available_attributes,
)

# Entities sharing one coordinator have no device I/O of their own to
# throttle; the coordinator is what rate-limits actual polling.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class XiaomiMiioFanBinarySensorDescription(BinarySensorEntityDescription):
    """Describes one read-only binary sensor derived from the fan's status."""

    attr_key: str = ""


# Only attributes confirmed boolean (from this component's own status
# classes, e.g. FanStatusP44/FanStatusZA5) on every model that exposes them.
BINARY_SENSOR_DESCRIPTIONS: tuple[XiaomiMiioFanBinarySensorDescription, ...] = (
    XiaomiMiioFanBinarySensorDescription(
        key="water_tank_empty",
        attr_key=ATTR_WATER_TANK_EMPTY,
        name="Water tank empty",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    XiaomiMiioFanBinarySensorDescription(
        key="error_detected",
        attr_key=ATTR_ERROR_DETECTED,
        name="Error detected",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    XiaomiMiioFanBinarySensorDescription(
        key="ac_power",
        attr_key=ATTR_AC_POWER,
        name="AC power",
        device_class=BinarySensorDeviceClass.PLUG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the fan's monitoring binary sensors from a config entry."""
    runtime_data = entry.runtime_data
    available = get_available_attributes(runtime_data.model)

    async_add_entities(
        XiaomiMiioFanBinarySensor(
            runtime_data.coordinator,
            description,
            device_name=runtime_data.name,
            model=runtime_data.model,
            device_unique_id=runtime_data.unique_id,
            sw_version=runtime_data.sw_version,
            raw_attribute=available[description.attr_key],
        )
        for description in BINARY_SENSOR_DESCRIPTIONS
        if description.attr_key in available
    )


class XiaomiMiioFanBinarySensor(XiaomiMiioFanMonitoringEntity, BinarySensorEntity):
    """A single read-only binary sensor derived from the fan's status."""

    entity_description: XiaomiMiioFanBinarySensorDescription

    def __init__(
        self,
        coordinator: XiaomiMiioFanDataUpdateCoordinator,
        description: XiaomiMiioFanBinarySensorDescription,
        *,
        device_name: str,
        model: str,
        device_unique_id: str,
        sw_version: str | None,
        raw_attribute: str,
    ) -> None:
        """Initialize the binary sensor."""
        self.entity_description = description
        super().__init__(
            coordinator,
            device_name=device_name,
            model=model,
            device_unique_id=device_unique_id,
            sw_version=sw_version,
            raw_attribute=raw_attribute,
            unique_id_suffix=description.key,
            name=description.name or description.key,
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if the condition this entity represents is active."""
        return self._raw_value
