"""Per-config-entry runtime data shared between this integration's platforms.

Built once in `__init__.py`'s `async_setup_entry`, before any platform (fan,
sensor, binary_sensor) is forwarded, so they all share the exact same miio
client object and coordinator instead of each connecting independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from miio import Device

    from .coordinator import XiaomiMiioFanDataUpdateCoordinator
    from .fan import XiaomiGenericDevice


@dataclass
class XiaomiMiioFanRuntimeData:
    """Everything a platform needs to set up entities for one config entry."""

    fan: Device
    fan_entity: XiaomiGenericDevice
    coordinator: XiaomiMiioFanDataUpdateCoordinator
    model: str
    name: str
    unique_id: str
    device_id: int | None
    sw_version: str | None
    retries: int
    preset_modes_override: list[str] | None
