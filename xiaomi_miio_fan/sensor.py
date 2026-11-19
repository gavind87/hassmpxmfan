"""Sensor platform for the Xiaomi Mi Smart Pedestal Fan integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import XiaomiMiioFanDataUpdateCoordinator
from .entity import XiaomiMiioFanMonitoringEntity
from .fan import (
    ATTR_BATTERY_CHARGE,
    ATTR_BATTERY_STATE,
    ATTR_BUTTON_PRESSED,
    ATTR_HUMIDITY,
    ATTR_TEMPERATURE,
    ATTR_USE_TIME,
    get_available_attributes,
)

# Entities sharing one coordinator have no device I/O of their own to
# throttle; the coordinator is what rate-limits actual polling.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class XiaomiMiioFanSensorDescription(SensorEntityDescription):
    """Describes one read-only sensor derived from the fan's status."""

    attr_key: str = ""


# Deliberately conservative: only attributes confirmed (from python-miio's
# own status classes, including the ones this component defines itself for
# ZA5/P44/etc.) to have the *same* type/meaning on every model that exposes
# them. `battery` was excluded - it's a 0-100 percentage on the original
# zhimi fans but a plain bool ("is a battery fitted") on the ZA5.
SENSOR_DESCRIPTIONS: tuple[XiaomiMiioFanSensorDescription, ...] = (
    XiaomiMiioFanSensorDescription(
        key="temperature",
        attr_key=ATTR_TEMPERATURE,
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XiaomiMiioFanSensorDescription(
        key="humidity",
        attr_key=ATTR_HUMIDITY,
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XiaomiMiioFanSensorDescription(
        key="use_time",
        attr_key=ATTR_USE_TIME,
        name="Use time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    XiaomiMiioFanSensorDescription(
        key="battery_state",
        attr_key=ATTR_BATTERY_STATE,
        name="Battery state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    XiaomiMiioFanSensorDescription(
        key="battery_charge",
        attr_key=ATTR_BATTERY_CHARGE,
        name="Battery charging state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    XiaomiMiioFanSensorDescription(
        key="button_pressed",
        attr_key=ATTR_BUTTON_PRESSED,
        name="Last button pressed",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the fan's monitoring sensors from a config entry."""
    runtime_data = entry.runtime_data
    available = get_available_attributes(runtime_data.model)

    async_add_entities(
        XiaomiMiioFanSensor(
            runtime_data.coordinator,
            description,
            device_name=runtime_data.name,
            model=runtime_data.model,
            device_unique_id=runtime_data.unique_id,
            sw_version=runtime_data.sw_version,
            raw_attribute=available[description.attr_key],
        )
        for description in SENSOR_DESCRIPTIONS
        if description.attr_key in available
    )


class XiaomiMiioFanSensor(XiaomiMiioFanMonitoringEntity, SensorEntity):
    """A single read-only sensor derived from the fan's status."""

    entity_description: XiaomiMiioFanSensorDescription

    def __init__(
        self,
        coordinator: XiaomiMiioFanDataUpdateCoordinator,
        description: XiaomiMiioFanSensorDescription,
        *,
        device_name: str,
        model: str,
        device_unique_id: str,
        sw_version: str | None,
        raw_attribute: str,
    ) -> None:
        """Initialize the sensor."""
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
    def native_value(self):
        """Return the current value of this sensor."""
        return self._raw_value
