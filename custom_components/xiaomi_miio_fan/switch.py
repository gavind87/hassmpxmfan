"""Switch platform for the Xiaomi Mi Smart Pedestal Fan integration.

On/off controls whose commands are uniform across the models that have them:
buzzer, child lock, anion/ionizer (ZA5), evaporative air cooler (P44) and the
on/off LED. Each delegates to the fan entity's existing command method.

Not exposed as switches: natural mode (state-dependent on the original zhimi
fans, not a plain device command) and multi-level LED brightness (zhimi, ZA5).
Oscillation angle and the turn-off timer live in `select.py` / `number.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import XiaomiMiioFanDataUpdateCoordinator
from .entity import XiaomiMiioFanMonitoringEntity
from .fan import (
    ATTR_AIR_COOLER,
    ATTR_BUZZER,
    ATTR_CHILD_LOCK,
    ATTR_IONIZER,
    ATTR_LED,
    FEATURE_SET_LED,
    get_available_attributes,
)
from .log import get_logger

_LOGGER = get_logger(__name__)

# Entities sharing one coordinator have no device I/O of their own to
# throttle; the coordinator is what rate-limits actual polling, and each
# write is a one-off command already guarded by the fan entity itself.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class XiaomiMiioFanSwitchDescription(SwitchEntityDescription):
    """Describes one on/off control, delegated to a method on the fan entity."""

    attr_key: str = ""
    turn_on_method: str = ""
    turn_off_method: str = ""
    turn_on_kwargs: dict[str, Any] = field(default_factory=dict)
    turn_off_kwargs: dict[str, Any] = field(default_factory=dict)
    # Skip models whose entity doesn't advertise this FEATURE_* flag.
    feature_flag: int = 0


SWITCH_DESCRIPTIONS: tuple[XiaomiMiioFanSwitchDescription, ...] = (
    XiaomiMiioFanSwitchDescription(
        key="buzzer",
        attr_key=ATTR_BUZZER,
        name="Buzzer",
        entity_category=EntityCategory.CONFIG,
        turn_on_method="async_set_buzzer_on",
        turn_off_method="async_set_buzzer_off",
    ),
    XiaomiMiioFanSwitchDescription(
        key="child_lock",
        attr_key=ATTR_CHILD_LOCK,
        name="Child lock",
        entity_category=EntityCategory.CONFIG,
        turn_on_method="async_set_child_lock_on",
        turn_off_method="async_set_child_lock_off",
    ),
    XiaomiMiioFanSwitchDescription(
        key="anion",
        attr_key=ATTR_IONIZER,
        name="Ionizer",
        entity_category=EntityCategory.CONFIG,
        turn_on_method="async_set_anion_on",
        turn_off_method="async_set_anion_off",
    ),
    XiaomiMiioFanSwitchDescription(
        key="air_cooler",
        attr_key=ATTR_AIR_COOLER,
        name="Evaporative cooling",
        entity_category=EntityCategory.CONFIG,
        turn_on_method="async_set_air_cooler_on",
        turn_off_method="async_set_air_cooler_off",
    ),
    # On/off LED (night light, display). The entity's legacy 3-level API treats
    # brightness 2 as "off" and anything else as "on" on every model carrying
    # FEATURE_SET_LED; models with a real 3-level/raw LED (zhimi, ZA5) use a
    # different flag and are intentionally not matched here.
    XiaomiMiioFanSwitchDescription(
        key="led",
        attr_key=ATTR_LED,
        name="LED",
        entity_category=EntityCategory.CONFIG,
        turn_on_method="async_set_led_brightness",
        turn_off_method="async_set_led_brightness",
        turn_on_kwargs={"brightness": 0},
        turn_off_kwargs={"brightness": 2},
        feature_flag=FEATURE_SET_LED,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the fan's on/off controls from a config entry."""
    runtime_data = entry.runtime_data
    available = get_available_attributes(runtime_data.model)

    async_add_entities(
        XiaomiMiioFanSwitch(
            runtime_data.coordinator,
            runtime_data.fan_entity,
            description,
            device_name=runtime_data.name,
            model=runtime_data.model,
            device_unique_id=runtime_data.unique_id,
            sw_version=runtime_data.sw_version,
            raw_attribute=available[description.attr_key],
        )
        for description in SWITCH_DESCRIPTIONS
        if description.attr_key in available
        and hasattr(runtime_data.fan_entity, description.turn_on_method)
        and (
            not description.feature_flag
            or runtime_data.fan_entity._device_features & description.feature_flag
        )
    )


class XiaomiMiioFanSwitch(XiaomiMiioFanMonitoringEntity, SwitchEntity):
    """An on/off control that delegates its commands to the fan entity."""

    entity_description: XiaomiMiioFanSwitchDescription

    def __init__(
        self,
        coordinator: XiaomiMiioFanDataUpdateCoordinator,
        fan_entity: Any,
        description: XiaomiMiioFanSwitchDescription,
        *,
        device_name: str,
        model: str,
        device_unique_id: str,
        sw_version: str | None,
        raw_attribute: str,
    ) -> None:
        """Initialize the switch."""
        self.entity_description = description
        self._fan_entity = fan_entity
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
        """Return the current on/off state."""
        return self._raw_value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the control on, via the fan entity's existing command logic."""
        await getattr(self._fan_entity, self.entity_description.turn_on_method)(
            **self.entity_description.turn_on_kwargs
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the control off, via the fan entity's existing command logic."""
        await getattr(self._fan_entity, self.entity_description.turn_off_method)(
            **self.entity_description.turn_off_kwargs
        )
        await self.coordinator.async_request_refresh()
