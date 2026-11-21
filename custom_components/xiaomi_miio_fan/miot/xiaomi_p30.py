"""MIoT client and status classes for the Xiaomi P30 fan.

Moved out of fan.py unchanged (Phase 6). Derived from
https://github.com/syssi/xiaomi_fan (Apache License 2.0); see NOTICE.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from miio.fan_common import FanException
from miio.miot_device import DeviceStatus, MiotDevice

from ..const import MODEL_FAN_XIAOMI_P30
from ._common import filter_request_fields


class OperationModeFanXiaomiP30(Enum):
    """Operation mode enum for FanXiaomiP30."""

    Normal = 0
    Nature = 1


class FanStatusXiaomiP30(DeviceStatus):
    """Container for status reports for FanXiaomiP30."""

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
        return OperationModeFanXiaomiP30(self.data["mode"]).name

    @property
    def fan_level(self) -> int:
        """Return the fan level."""
        return self.data["fan_level"]

    @property
    def fan_speed(self) -> int:
        """Return the fan speed."""
        return self.data["fan_speed"]

    @property
    def percentage(self) -> int:
        """Return the current speed as a percentage."""
        return self.data["fan_speed"]

    @property
    def horizontal_swing(self) -> bool:
        """Return the horizontal swing state."""
        return self.data["horizontal_swing"]

    @property
    def oscillate(self) -> bool:
        """Return the oscillation state."""
        return self.data["horizontal_swing"]

    @property
    def horizontal_swing_angle(self) -> int:
        """Return the horizontal swing angle."""
        return self.data["horizontal_swing_angle"]

    @property
    def angle(self) -> int:
        """Return the oscillation angle."""
        return self.data["horizontal_swing_angle"]

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
    def delay(self) -> bool:
        """Return the delay state."""
        return self.data["delay"]

    @property
    def delay_time(self) -> int:
        """Return the delay time."""
        return self.data["delay_time"]

    @property
    def delay_remain_time(self) -> int:
        """Return the remaining delay time."""
        return self.data["delay_remain_time"]


class FanXiaomiP30(MiotDevice):
    """Main class representing the Xiaomi Fan P30 (xiaomi.fan.p30)."""

    # https://miot-spec.org/miot-spec-v2/instance?type=urn:miot-spec-v2:device:fan:0000A005:xiaomi-p30:1:0000D062
    mapping = {
        "power": {"siid": 2, "piid": 1},
        "fault": {"siid": 2, "piid": 2},
        "mode": {"siid": 2, "piid": 3},
        "fan_level": {"siid": 2, "piid": 4},
        "fan_speed": {"siid": 2, "piid": 5},
        "horizontal_swing": {"siid": 2, "piid": 6},
        "horizontal_swing_angle": {"siid": 2, "piid": 7},
        "led": {"siid": 5, "piid": 1},
        "buzzer": {"siid": 7, "piid": 1},
        "child_lock": {"siid": 8, "piid": 1},
        "delay": {"siid": 9, "piid": 1},
        "delay_time": {"siid": 9, "piid": 2},
        "delay_remain_time": {"siid": 9, "piid": 4},
        "turn_left": {"siid": 2, "aiid": 4},
        "turn_right": {"siid": 2, "aiid": 5},
    }

    def __init__(
        self,
        ip: str | None = None,
        token: str | None = None,
        start_id: int = 0,
        debug: int = 0,
        lazy_discover: bool = True,
        timeout: int = 5,
        model: str = MODEL_FAN_XIAOMI_P30,
    ):
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
        return FanStatusXiaomiP30(
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

    def set_speed(self, speed: int):
        """Set fan speed in percent (1-100), used in direct/normal mode."""
        if speed < 1 or speed > 100:
            raise FanException(f"Invalid speed: {speed}")

        return self.set_property("fan_speed", speed)

    def set_fan_level(self, level: int):
        """Set the discrete fan level (1-4)."""
        if level < 1 or level > 4:
            raise FanException(f"Invalid fan level: {level}")

        return self.set_property("fan_level", level)

    def set_oscillate(self, oscillate: bool):
        """Set horizontal oscillation on/off."""
        return self.set_property("horizontal_swing", oscillate)

    def set_angle(self, angle: int):
        """Set the horizontal oscillation angle."""
        if angle not in [30, 60, 90, 120, 140]:
            raise FanException(
                "Unsupported angle. Supported values: "
                + ", ".join(str(i) for i in [30, 60, 90, 120, 140])
            )

        return self.set_property("horizontal_swing_angle", angle)

    def set_buzzer(self, buzzer: bool):
        """Set buzzer on/off."""
        return self.set_property("buzzer", buzzer)

    def set_child_lock(self, lock: bool):
        """Set child lock on/off."""
        return self.set_property("child_lock", lock)

    def set_light(self, light: bool):
        """Set indicator LED on/off."""
        return self.set_property("led", light)

    def set_mode(self, mode: OperationModeFanXiaomiP30):
        """Set mode."""
        return self.set_property("mode", mode.value)

    def delay_off(self, minutes: int):
        """Set delay off in minutes (0-480)."""
        if minutes < 0 or minutes > 480:
            raise FanException(f"Invalid value for a delayed turn off: {minutes}")

        return self.set_property("delay_time", minutes)

    def turn(self, direction: str):
        """Turn to the given direction."""
        if direction == "left":
            return self.call_action("turn_left")
        elif direction == "right":
            return self.call_action("turn_right")
        else:
            raise FanException(
                "Unsupported direction. Supported values: "
                + ", ".join(["left", "right"])
            )
