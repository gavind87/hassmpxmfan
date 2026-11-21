"""Number platform: delay-off (sleep) timer, in minutes.

Unit audit (done against python-miio 0.5.12 and this repo's `miot/` clients):
every client's `delay_off` takes *minutes* except the original zhimi `Fan`
and the ZA5, which take seconds - and those two entity classes already
multiply by 60 in `async_set_delay_off`. So `async_set_delay_off` is
uniformly minutes at the entity level, matching the service's contract; the
"P5 is different" suspicion in earlier notes was just the entity layer
compensating for the client layer. Only the allowed maximum differs.

Value is assumed (last value set from here), not read back: the status field
that looks like a countdown is seconds on some models, minutes on others, and
a configured-time field on a third group, so there is no single honest
readback. Setting 0 cancels the timer.
"""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import XiaomiMiioFanDataUpdateCoordinator
from .entity import XiaomiMiioFanMonitoringEntity
from .log import get_logger

_LOGGER = get_logger(__name__)

PARALLEL_UPDATES = 0

DEFAULT_MAX_MINUTES = 480
# Largest value each client accepts, where it differs from 480.
MAX_MINUTES_BY_ENTITY_CLASS: dict[str, int] = {
    "XiaomiFan": 600,  # zhimi: no client limit; matches the service's cap
    "XiaomiFanZA5": 600,
    "XiaomiFanLeshow": 540,
    "XiaomiFanP28": 720,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the delay-off timer if this model's entity supports it."""
    runtime_data = entry.runtime_data
    fan_entity = runtime_data.fan_entity
    if not hasattr(fan_entity, "async_set_delay_off"):
        return

    async_add_entities(
        [
            XiaomiMiioFanDelayOff(
                runtime_data.coordinator,
                fan_entity,
                MAX_MINUTES_BY_ENTITY_CLASS.get(
                    type(fan_entity).__name__, DEFAULT_MAX_MINUTES
                ),
                device_name=runtime_data.name,
                model=runtime_data.model,
                device_unique_id=runtime_data.unique_id,
                sw_version=runtime_data.sw_version,
            )
        ]
    )


class XiaomiMiioFanDelayOff(XiaomiMiioFanMonitoringEntity, NumberEntity):
    """Schedule the fan to switch itself off after N minutes."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = 0
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_assumed_state = True
    _attr_icon = "mdi:timer-off-outline"

    def __init__(
        self,
        coordinator: XiaomiMiioFanDataUpdateCoordinator,
        fan_entity,
        max_minutes: int,
        *,
        device_name: str,
        model: str,
        device_unique_id: str,
        sw_version: str | None,
    ) -> None:
        """Initialize the number."""
        self._fan_entity = fan_entity
        self._attr_native_max_value = max_minutes
        self._attr_native_value: float | None = None
        super().__init__(
            coordinator,
            device_name=device_name,
            model=model,
            device_unique_id=device_unique_id,
            sw_version=sw_version,
            raw_attribute="",
            unique_id_suffix="delay_off",
            name="Turn-off timer",
        )

    @property
    def available(self) -> bool:
        """Available whenever the device is reachable (there is no readback)."""
        return self.coordinator.last_update_success

    async def async_set_native_value(self, value: float) -> None:
        """Start (or, with 0, cancel) the timer."""
        minutes = int(value)
        await self._fan_entity.async_set_delay_off(minutes)
        self._attr_native_value = minutes
        self.async_write_ha_state()
