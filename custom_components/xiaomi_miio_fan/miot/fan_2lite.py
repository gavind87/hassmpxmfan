"""MIoT client and status classes for the 2Lite fan.

Moved out of fan.py unchanged (Phase 6). Derived from
https://github.com/syssi/xiaomi_fan (Apache License 2.0); see NOTICE.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from miio.fan_common import FanException
from miio.miot_device import DeviceStatus, MiotDevice

from ..const import MODEL_FAN_2LITE
from ._common import filter_request_fields

FAN_2LITE_SPEED_COUNT = 3


class OperationModeFan2Lite(Enum):
    """Operation mode enum for Fan2Lite."""

    Straight = 0
    Natural = 1


class FanStatus2Lite(DeviceStatus):
    """Container for status reports for Fan2Lite."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize."""
        self.data = data

    @property
    def power(self) -> bool:
        """Return the power state."""
        return self.data["power"]

    @property
    def fault(self) -> int:
        """Return the fault code."""
        return self.data["fault"]

    @property
    def mode(self) -> str:
        """Return the operation mode."""
        return OperationModeFan2Lite(self.data["mode"]).name

    @property
    def fan_level(self) -> int:
        """Return the fan level."""
        return self.data["fan_level"]

    @property
    def horizontal_swing(self) -> bool:
        """Return the horizontal swing state."""
        return self.data["horizontal_swing"]

    @property
    def led(self) -> bool:
        """Return the LED state."""
        return self.data["led"]

    @property
    def buzzer(self) -> bool:
        """Return the buzzer state."""
        return self.data["buzzer"]

    @property
    def child_lock(self) -> bool:
        """Return the child lock state."""
        return self.data["child_lock"]

    @property
    def delay_time(self) -> int:
        """Return the delay time."""
        return self.data["delay_time"]


class Fan2Lite(MiotDevice):
    """Main class representing the Mi Smart Standing Fan 2 Lite (xiaomi.fan.2lite)."""

    mapping = {
        # urn:miot-spec-v2:device:fan:0000A005:xiaomi-2lite:1
        "power": {"siid": 2, "piid": 1},
        "fault": {"siid": 2, "piid": 2},
        "mode": {"siid": 2, "piid": 3},
        "fan_level": {"siid": 2, "piid": 4},
        "horizontal_swing": {"siid": 2, "piid": 6},
        "led": {"siid": 5, "piid": 1},
        "buzzer": {"siid": 7, "piid": 1},
        "child_lock": {"siid": 8, "piid": 1},
        "delay": {"siid": 9, "piid": 1},
        "delay_time": {"siid": 9, "piid": 2},
    }

    def __init__(
        self,
        ip: str | None = None,
        token: str | None = None,
        start_id: int = 0,
        debug: int = 0,
        lazy_discover: bool = True,
        timeout: int = 5,
        model: str = MODEL_FAN_2LITE,
    ) -> None:
        """Initialize."""
        super().__init__(
            ip, token, start_id, debug, lazy_discover, timeout, model=model
        )

    def get_properties_for_mapping(self, *, max_properties=15) -> list:
        """Retrieve raw properties based on mapping."""
        mapping = self._get_mapping()

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
        return FanStatus2Lite(
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
        """Set fan level (0-2)."""
        if level not in range(FAN_2LITE_SPEED_COUNT):
            raise FanException(f"Invalid fan level: {level}")
        return self.set_property("fan_level", level)

    def set_oscillate(self, oscillate: bool):
        """Set horizontal oscillation on/off."""
        return self.set_property("horizontal_swing", oscillate)

    def set_buzzer(self, buzzer: bool):
        """Set buzzer on/off."""
        return self.set_property("buzzer", buzzer)

    def set_child_lock(self, lock: bool):
        """Set child lock on/off."""
        return self.set_property("child_lock", lock)

    def set_light(self, light: bool):
        """Set indicator state."""
        return self.set_property("led", light)

    def set_mode(self, mode: OperationModeFan2Lite):
        """Set mode."""
        return self.set_property("mode", mode.value)

    def delay_off(self, minutes: int):
        """Set delay off in minutes (0-480). 0 deactivates the timer."""
        if minutes < 0 or minutes > 480:
            raise FanException(f"Invalid value for a delayed turn off: {minutes}")
        if minutes == 0:
            return self.set_property("delay", False)
        self.set_property("delay_time", minutes)
        return self.set_property("delay", True)
