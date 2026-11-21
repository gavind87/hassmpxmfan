"""MIoT client and status classes for the P33 fan.

Moved out of fan.py unchanged (Phase 6). Derived from
https://github.com/syssi/xiaomi_fan (Apache License 2.0); see NOTICE.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from miio.fan_common import FanException
from miio.fan_common import MoveDirection as FanMoveDirection
from miio.miot_device import DeviceStatus, MiotDevice

from ..const import MODEL_FAN_P33


class OperationModeFanP33(Enum):
    """Operation mode enum for FanP33."""

    Normal = 0
    Nature = 1


class FanStatusP33(DeviceStatus):
    """Container for status reports for FanP33."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize with response from Fan (dmaker.fan.p33, fw: 2.1.3).

        {'did': 'power', 'siid': 2, 'piid': 1, 'code': 0, 'value': True},
        {'did': 'fan_level', 'siid': 2, 'piid': 2, 'code': 0, 'value': 1},
        {'did': 'swing_mode', 'siid': 2, 'piid': 4, 'code': 0, 'value': False},
        {'did': 'swing_mode_angle', 'siid': 2, 'piid': 5, 'code': 0, 'value': 120},
        {'did': 'mode', 'siid': 2, 'piid': 3, 'code': 0, 'value': 1},
        {'did': 'power_off_time', 'siid': 3, 'piid': 1, 'code': 0, 'value': 0},
        {'did': 'child_lock', 'siid': 7, 'piid': 1, 'code': 0, 'value': False},
        {'did': 'light', 'siid': 4, 'piid': 1, 'code': 0, 'value': True},
        {'did': 'buzzer', 'siid': 5, 'piid': 1, 'code': 0, 'value': True},
        {'did': 'set_move', 'siid': 6, 'piid': 1, 'code': -4003},
        {'did': 'fan_speed', 'siid': 2, 'piid': 6, 'code': 0, 'value': 20},
        """
        self.data = data

    @property
    def buzzer(self) -> bool:
        """Return the buzzer state."""
        return self.data["buzzer"]

    @property
    def child_lock(self) -> bool:
        """Return the child lock state."""
        return self.data["child_lock"]

    @property
    def fan_level(self) -> int:
        """Return the fan level."""
        return self.data["fan_level"]

    @property
    def percentage(self) -> int:
        """Return the current speed as a percentage."""
        return self.data["fan_speed"]

    @property
    def light(self) -> bool:
        """Return the light state."""
        return self.data["light"]

    @property
    def led(self) -> bool:
        """Return the LED state."""
        return self.light

    @property
    def mode(self) -> str:
        """Return the operation mode."""
        return OperationModeFanP33(self.data["mode"]).name

    @property
    def power(self) -> bool:
        """Return the power state."""
        return self.data["power"]

    @property
    def delay_off_countdown(self) -> int:
        """Return the delay off countdown."""
        return self.data["power_off_time"]

    @property
    def oscillate(self) -> bool:
        """Return the oscillation state."""
        return self.data["swing_mode"]

    @property
    def angle(self) -> int:
        """Return the oscillation angle."""
        return self.data["swing_mode_angle"]


class FanP33(MiotDevice):
    """Main class representing the Xiaomi Fan P33 (dmaker.fan.p33)."""

    mapping = {
        # https://miot-spec.org/miot-spec-v2/instance?type=urn:miot-spec-v2:device:fan:0000A005:dmaker-p33:1
        "power": {"siid": 2, "piid": 1},
        "fan_level": {"siid": 2, "piid": 2},
        "swing_mode": {"siid": 2, "piid": 4},
        "swing_mode_angle": {"siid": 2, "piid": 5},
        "mode": {"siid": 2, "piid": 3},
        "power_off_time": {"siid": 3, "piid": 1},
        "child_lock": {"siid": 7, "piid": 1},
        "light": {"siid": 4, "piid": 1},
        "buzzer": {"siid": 5, "piid": 1},
        "set_move": {"siid": 6, "piid": 1},
        "fan_speed": {"siid": 2, "piid": 6},
    }

    def __init__(
        self,
        ip: str | None = None,
        token: str | None = None,
        start_id: int = 0,
        debug: int = 0,
        lazy_discover: bool = True,
        model: str = MODEL_FAN_P33,
    ) -> None:
        """Initialize."""
        super().__init__(ip, token, start_id, debug, lazy_discover, model=model)

    def status(self):
        """Retrieve properties."""
        return FanStatusP33(
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
        """Set fan speed, needed to wrap next method."""
        return self.set_percentage(speed)

    def set_percentage(self, percentage: int):
        """Set fan percentage."""
        if percentage < 0 or percentage > 100:
            raise FanException(f"Invalid percentage: {percentage}")

        return self.set_property("fan_speed", percentage)

    def set_angle(self, angle: int):
        """Set the oscillation angle."""
        if angle not in [30, 60, 90, 120, 140]:
            raise FanException(
                "Unsupported angle. Supported values: "
                + ", ".join(f"{i}" for i in [30, 60, 90, 120, 140])
            )

        return self.set_property("swing_mode_angle", angle)

    def set_oscillate(self, oscillate: bool):
        """Set oscillate on/off."""
        if oscillate:
            return self.set_property("swing_mode", True)
        else:
            return self.set_property("swing_mode", False)

    def set_buzzer(self, buzzer: bool):
        """Set buzzer on/off."""
        if buzzer:
            return self.set_property("buzzer", True)
        else:
            return self.set_property("buzzer", False)

    def set_child_lock(self, lock: bool):
        """Set child lock on/off."""
        self.status()
        return self.set_property("child_lock", lock)

    def set_light(self, light: bool):
        """Set indicator state."""
        return self.set_property("light", light)

    def set_led(self, led: bool):
        """Set indicator state through the common fan LED interface."""
        return self.set_light(led)

    def set_mode(self, mode: OperationModeFanP33):
        """Set mode."""
        return self.set_property("mode", OperationModeFanP33[mode.name].value)

    def delay_off(self, minutes: int):
        """Set delay off minutes."""

        if minutes < 0 or minutes > 480:
            raise FanException(f"Invalid value for a delayed turn off: {minutes}")

        return self.set_property("power_off_time", minutes)

    def set_rotate(self, direction: FanMoveDirection):
        """Rotate fan 7.5 degrees horizontally to given direction."""
        # Values for P33
        # { "value": 0, "description": "NONE" },
        # { "value": 1, "description": "LEFT" },
        # { "value": 2, "description": "RIGHT" }
        value = 0
        if direction == FanMoveDirection.Left:
            value = 1
        elif direction == FanMoveDirection.Right:
            value = 2
        return self.set_property("set_move", value)
