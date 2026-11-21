"""Shared polling coordinator for a fan's read-only monitoring data.

The fan entity itself (`fan.py`) keeps doing its own, separate status
polling with its own retry-tolerance and IP auto-heal, since it drives the
device and that logic is already tested on real hardware. This coordinator
is only used by the read-only `sensor`/`binary_sensor` entities, which share
one poller instead of each connecting independently, and which can simply go
unavailable on failure rather than needing their own retry/heal handling.

Because `__init__.py` builds the fan client once and hands the *same* object
to both the fan entity and this coordinator, a successful IP auto-heal on the
fan entity's side is automatically picked up by the next coordinator poll too
- there is only ever one client object per config entry.

Known, accepted tradeoffs of sharing that one client between two independent
pollers (the fan entity's own `should_poll` loop and this coordinator), rather
than migrating the fan entity onto this coordinator too:
- The device gets polled roughly twice as often as before.
- The underlying `MiIOProtocol` object mutates a couple of plain instance
  attributes (a running message ID, a timestamp) per call and isn't
  documented as thread-safe; two polls landing at the same instant could in
  theory race on those. Each call already has its own retry logic, so the
  realistic worst case is an occasional single failed/retried poll, not
  corrupted state - but this is worth revisiting if real-world use shows
  otherwise, by migrating the fan entity onto this coordinator as well.
"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from miio import DeviceException

_LOGGER = logging.getLogger(__name__)

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=30)


class XiaomiMiioFanDataUpdateCoordinator(DataUpdateCoordinator):
    """Poll a fan's status once and share it with its monitoring entities."""

    def __init__(self, hass: HomeAssistant, fan: Any, name: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self.fan = fan

    async def _async_update_data(self) -> Any:
        """Fetch the fan's current status."""
        try:
            return await self.hass.async_add_executor_job(self.fan.status)
        except DeviceException as ex:
            raise UpdateFailed(str(ex)) from ex
