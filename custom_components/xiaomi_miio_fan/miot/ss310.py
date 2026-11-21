"""MIoT client and status classes for the SS310 fan.

Moved out of fan.py unchanged (Phase 6). Derived from
https://github.com/syssi/xiaomi_fan (Apache License 2.0); see NOTICE.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from miio.fan_common import FanException
from miio.miot_device import DeviceStatus, MiotDevice

from ..const import MODEL_FAN_LESHOW_SS310
from ._common import filter_request_fields


class OperationModeFanSS310(Enum):
    """Operation mode enum for FanSS310."""

    Normal = 0
    Sleep = 1


class FanStatusSS310(DeviceStatus):
    """Container for status reports for FanSS310."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize."""
        self.data = data

    @property
    def power(self) -> bool:
        """Return the power state."""
        return self.data["power"]

    @property
    def mode(self) -> str:
        """Return the operation mode."""
        return OperationModeFanSS310(self.data["mode"]).name

    @property
    def fan_level(self) -> int:
        """Return the fan level (one of 1, 25, 50, 75, 100)."""
        return self.data["fan_level"]

    @property
    def horizontal_swing(self) -> bool:
        """Return the horizontal swing state."""
        return self.data["horizontal_swing"]

    @property
    def vertical_swing(self) -> bool:
        """Return the vertical swing state."""
        return self.data["vertical_swing"]


class FanSS310(MiotDevice):
    """Main class representing the Rosou SS310 Ventilator (leshow.fan.ss310)."""

    mapping = {
        # urn:miot-spec-v2:device:fan:0000A005:leshow-ss310:1
        "power": {"siid": 2, "piid": 1},
        "fan_level": {"siid": 2, "piid": 2},
        "mode": {"siid": 2, "piid": 3},
        "horizontal_swing": {"siid": 2, "piid": 4},
        "vertical_swing": {"siid": 2, "piid": 5},
    }

    def __init__(
        self,
        ip: str | None = None,
        token: str | None = None,
        start_id: int = 0,
        debug: int = 0,
        lazy_discover: bool = True,
        timeout: int = 5,
        model: str = MODEL_FAN_LESHOW_SS310,
    ) -> None:
        """Initialize."""
        super().__init__(
            ip, token, start_id, debug, lazy_discover, timeout, model=model
        )

    # backported and adapted from current master
    def get_properties_for_mapping(self, *, max_properties=15) -> list:
        """Retrieve raw properties based on mapping."""
        mapping = self._get_mapping()

        # We send property key in "did" because it's sent back via response and we can identify the property.
        properties = [
            {"did": k, **filter_request_fields(v)}
            for k, v in mapping.items()
            if "aiid" not in v and ("access" not in v or "read" in v["access"])
        ]

        return self.get_properties(
            properties, property_getter="get_properties", max_properties=max_properties
        )

    def status(self):
        """Retrieve properties."""
        return FanStatusSS310(
            {
                prop["did"]: prop["value"] if prop["code"] == 0 else None
                for prop in self.get_properties_for_mapping()
            }
        )

    def on(self):
        """Power on."""
        return self.set_property("power", True)

    def off(self):
        """Power off."""
        return self.set_property("power", False)

    def set_fan_level(self, level: int):
        """Set fan level. Only 1, 25, 50, 75 or 100 are valid."""
        if level not in (1, 25, 50, 75, 100):
            raise FanException(f"Invalid fan level: {level}")
        return self.set_property("fan_level", level)

    def set_mode(self, mode: OperationModeFanSS310):
        """Set mode."""
        return self.set_property("mode", mode.value)

    def set_horizontal_oscillation(self, oscillate: bool):
        """Set horizontal oscillation on/off."""
        return self.set_property("horizontal_swing", oscillate)

    def set_vertical_oscillation(self, oscillate: bool):
        """Set vertical oscillation on/off."""
        return self.set_property("vertical_swing", oscillate)
