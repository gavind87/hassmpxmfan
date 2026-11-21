"""Select platform: horizontal oscillation angle.

Every MIoT model only accepts a fixed set of swing angles (anything else is
rejected by its client with a `FanException`), and the sets differ per model,
so a select with the exact options is a better fit than a free-form number.
The table below was taken from each client's own `set_angle` validation
(python-miio's `SUPPORTED_ANGLES` for P5/P9/P10/P11, and this repo's `miot/`
modules for the rest).

The original zhimi fans accept any angle 0-120 but are limited here to the
30/60/90/120 steps the Mi Home app offers. Deliberately not covered: the 1C,
whose client has no `set_angle` at all (its feature flag is a pre-existing
over-claim); the `fan_set_oscillation_angle` service still takes any value.
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import MODEL_FAN_P9
from .coordinator import XiaomiMiioFanDataUpdateCoordinator
from .entity import XiaomiMiioFanMonitoringEntity
from .fan import ATTR_ANGLE, FEATURE_SET_OSCILLATION_ANGLE, get_available_attributes
from .log import get_logger

_LOGGER = get_logger(__name__)

PARALLEL_UPDATES = 0

_ANGLES_30_TO_140 = (30, 60, 90, 120, 140)
_ANGLES_30_TO_150 = (30, 60, 90, 120, 150)
_ANGLES_30_TO_120 = (30, 60, 90, 120)
_ANGLES_30_TO_90 = (30, 60, 90)

# Keyed by entity class name (the model -> class lookup lives in fan.py).
ANGLES_BY_ENTITY_CLASS: dict[str, tuple[int, ...]] = {
    # zhimi clients accept any 0-120, but the Mi Home app (and the device's
    # own oscillation) only uses these four steps.
    "XiaomiFan": _ANGLES_30_TO_120,
    "XiaomiFanP5": _ANGLES_30_TO_140,
    "XiaomiFanZA5": _ANGLES_30_TO_120,
    "XiaomiFanP33": _ANGLES_30_TO_140,
    "XiaomiFanP39": _ANGLES_30_TO_140,
    "XiaomiFanXiaomiP30": _ANGLES_30_TO_140,
    "XiaomiFanP45": _ANGLES_30_TO_150,
    "XiaomiFanP28": _ANGLES_30_TO_150,
    "XiaomiFanP70": _ANGLES_30_TO_120,
    "XiaomiFanP76": _ANGLES_30_TO_120,
    "XiaomiFanP51": _ANGLES_30_TO_120,
    "XiaomiFanP43": _ANGLES_30_TO_90,
    "XiaomiFanP85": _ANGLES_30_TO_90,
}


def supported_angles(fan_entity) -> tuple[int, ...] | None:
    """Return the swing angles a fan entity accepts, or None if not a select."""
    if not fan_entity._device_features & FEATURE_SET_OSCILLATION_ANGLE:
        return None
    name = type(fan_entity).__name__
    if name == "XiaomiFanMiot":
        # P9 tops out at 150; P10/P11 (and the P18/P30/P15 aliases) at 140.
        return (
            _ANGLES_30_TO_150
            if fan_entity._model == MODEL_FAN_P9
            else _ANGLES_30_TO_140
        )
    return ANGLES_BY_ENTITY_CLASS.get(name)


def _label(angle: int) -> str:
    return f"{angle}°"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the oscillation-angle select if this model supports it."""
    runtime_data = entry.runtime_data
    angles = supported_angles(runtime_data.fan_entity)
    if angles is None:
        return

    raw_attribute = get_available_attributes(runtime_data.model).get(ATTR_ANGLE)
    async_add_entities(
        [
            XiaomiMiioFanAngleSelect(
                runtime_data.coordinator,
                runtime_data.fan_entity,
                angles,
                device_name=runtime_data.name,
                model=runtime_data.model,
                device_unique_id=runtime_data.unique_id,
                sw_version=runtime_data.sw_version,
                raw_attribute=raw_attribute or ATTR_ANGLE,
            )
        ]
    )


class XiaomiMiioFanAngleSelect(XiaomiMiioFanMonitoringEntity, SelectEntity):
    """Pick the horizontal oscillation angle."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:angle-acute"

    def __init__(
        self,
        coordinator: XiaomiMiioFanDataUpdateCoordinator,
        fan_entity,
        angles: tuple[int, ...],
        *,
        device_name: str,
        model: str,
        device_unique_id: str,
        sw_version: str | None,
        raw_attribute: str,
    ) -> None:
        """Initialize the select."""
        self._fan_entity = fan_entity
        self._attr_options = [_label(angle) for angle in angles]
        super().__init__(
            coordinator,
            device_name=device_name,
            model=model,
            device_unique_id=device_unique_id,
            sw_version=sw_version,
            raw_attribute=raw_attribute,
            unique_id_suffix="oscillation_angle",
            name="Oscillation angle",
        )

    @property
    def current_option(self) -> str | None:
        """Return the active angle, if it is one of the selectable values."""
        label = _label(self._raw_value) if isinstance(self._raw_value, int) else None
        return label if label in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        """Send the chosen angle to the device."""
        await self._fan_entity.async_set_oscillation_angle(int(option.rstrip("°")))
        await self.coordinator.async_request_refresh()
