"""Button platform: nudge the fan head left or right.

Two families support this:
- zhimi (`XiaomiFan`) and the P5 expose `set_rotate`, which turns the head by
  5 degrees per press. The fan entity reaches it through `async_set_direction`
  ("left"/"right"), which also switches oscillation off first (a fixed nudge
  is meaningless while the head is sweeping).
- Models flagged FEATURE_TURN (P30, P43, P45, P51, P70, P76, P85) take
  `async_turn("left"/"right")`.

Not exposed: P76/P70 `async_set_direction` (that means vertical oscillation
there) and the up/down turns, whose semantics are unverified.
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import XiaomiMiioFanDataUpdateCoordinator
from .entity import XiaomiMiioFanMonitoringEntity
from .fan import FEATURE_TURN
from .log import get_logger

_LOGGER = get_logger(__name__)

PARALLEL_UPDATES = 0

# Entity classes whose `async_set_direction` is the real left/right rotate.
ROTATE_VIA_DIRECTION: dict[str, bool] = {"XiaomiFan": True, "XiaomiFanP5": True}

DIRECTIONS = (
    ("left", "Rotate left", "mdi:rotate-left"),
    ("right", "Rotate right", "mdi:rotate-right"),
)


def _rotate_method(fan_entity):
    """Return the coroutine function that rotates the head, or None."""
    if ROTATE_VIA_DIRECTION.get(type(fan_entity).__name__):
        return fan_entity.async_set_direction
    if fan_entity._device_features & FEATURE_TURN and hasattr(fan_entity, "async_turn"):
        return fan_entity.async_turn
    return None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the rotate buttons for models that support them."""
    runtime_data = entry.runtime_data
    method = _rotate_method(runtime_data.fan_entity)
    if method is None:
        return

    async_add_entities(
        XiaomiMiioFanRotateButton(
            runtime_data.coordinator,
            method,
            direction,
            name,
            icon,
            device_name=runtime_data.name,
            model=runtime_data.model,
            device_unique_id=runtime_data.unique_id,
            sw_version=runtime_data.sw_version,
        )
        for direction, name, icon in DIRECTIONS
    )


class XiaomiMiioFanRotateButton(XiaomiMiioFanMonitoringEntity, ButtonEntity):
    """Turn the fan head one step in a direction."""

    def __init__(
        self,
        coordinator: XiaomiMiioFanDataUpdateCoordinator,
        method,
        direction: str,
        name: str,
        icon: str,
        *,
        device_name: str,
        model: str,
        device_unique_id: str,
        sw_version: str | None,
    ) -> None:
        """Initialize the button."""
        self._method = method
        self._direction = direction
        self._attr_icon = icon
        super().__init__(
            coordinator,
            device_name=device_name,
            model=model,
            device_unique_id=device_unique_id,
            sw_version=sw_version,
            raw_attribute="",
            unique_id_suffix=f"rotate_{direction}",
            name=name,
        )

    @property
    def available(self) -> bool:
        """Available whenever the device is reachable (buttons have no state)."""
        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        """Rotate one step."""
        await self._method(self._direction)
        await self.coordinator.async_request_refresh()
