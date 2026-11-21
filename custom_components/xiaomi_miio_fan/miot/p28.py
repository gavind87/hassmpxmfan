"""MIoT client and status classes for the P28 fan.

Moved out of fan.py unchanged (Phase 6). Derived from
https://github.com/syssi/xiaomi_fan (Apache License 2.0); see NOTICE.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from miio.fan_common import FanException
from miio.miot_device import DeviceStatus, MiotDevice

from ..const import MODEL_FAN_P28
from ._common import filter_request_fields


class OperationModeFanP28(Enum):
    """Operation mode enum for FanP28."""

    Straight = 0
    Natural = 1
    Smart = 2
    Sleep = 3


class FanStatusP28(DeviceStatus):
    """Container for status reports for FanP28."""

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
        return OperationModeFanP28(self.data["mode"]).name

    @property
    def fan_level(self) -> int:
        """Return the discrete fan level (1-4)."""
        return self.data["fan_level"]

    @property
    def speed(self) -> int:
        """Return the continuous fan speed (1-100, dm-service speed-level)."""
        return self.data["speed"]

    @property
    def horizontal_swing(self) -> bool:
        """Return the horizontal swing state."""
        return self.data["horizontal_swing"]

    @property
    def horizontal_swing_angle(self) -> int:
        """Return the horizontal swing angle."""
        return self.data["horizontal_swing_angle"]

    @property
    def vertical_swing(self) -> bool:
        """Return the vertical swing state."""
        return self.data["vertical_swing"]

    @property
    def vertical_swing_angle(self) -> int:
        """Return the vertical swing angle."""
        return self.data["vertical_swing_angle"]

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
        """Return the delay time in minutes."""
        return self.data["delay_time"]

    @property
    def temperature(self) -> Any:
        """Return the temperature in degrees Celsius."""
        return self.data["temperature"]

    @property
    def humidity(self) -> Any:
        """Return the relative humidity in percent."""
        return self.data["humidity"]


class FanP28(MiotDevice):
    """Main class representing the Xiaomi/Mijia Fan P28 (dmaker.fan.p28)."""

    mapping = {
        # urn:miot-spec-v2:device:fan:0000A005:dmaker-p28:1
        "power": {"siid": 2, "piid": 1},
        "fan_level": {"siid": 2, "piid": 2},
        "mode": {"siid": 2, "piid": 3},
        "horizontal_swing": {"siid": 2, "piid": 4},
        "horizontal_swing_angle": {"siid": 2, "piid": 5},
        "vertical_swing": {"siid": 2, "piid": 7},
        "vertical_swing_angle": {"siid": 2, "piid": 8},
        "led": {"siid": 4, "piid": 1},
        "buzzer": {"siid": 5, "piid": 1},
        "child_lock": {"siid": 7, "piid": 1},
        "delay_time": {"siid": 3, "piid": 1},
        # Vendor dm-service: continuous 1-100 speed. This, not fan_level,
        # backs Home Assistant's percentage control.
        "speed": {"siid": 8, "piid": 1},
        "temperature": {"siid": 9, "piid": 1},
        "humidity": {"siid": 9, "piid": 2},
    }

    def __init__(
        self,
        ip: str | None = None,
        token: str | None = None,
        start_id: int = 0,
        debug: int = 0,
        lazy_discover: bool = True,
        timeout: int = 5,
        model: str = MODEL_FAN_P28,
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
        return FanStatusP28(
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
        """Set the continuous fan speed (1-100, dm-service speed-level)."""
        if speed < 1 or speed > 100:
            raise FanException(f"Invalid speed: {speed}")
        return self.set_property("speed", speed)

    def set_fan_level(self, level: int):
        """Set the discrete fan level (1-4)."""
        if level not in [1, 2, 3, 4]:
            raise FanException(f"Invalid fan level: {level}")
        return self.set_property("fan_level", level)

    def set_oscillate(self, oscillate: bool):
        """Set horizontal oscillation on/off."""
        return self.set_property("horizontal_swing", oscillate)

    def set_angle(self, angle: int):
        """Set the horizontal oscillation angle."""
        if angle not in [30, 60, 90, 120, 150]:
            raise FanException(
                "Unsupported angle. Supported values: "
                + ", ".join(str(i) for i in [30, 60, 90, 120, 150])
            )
        return self.set_property("horizontal_swing_angle", angle)

    def set_vertical_oscillate(self, oscillate: bool):
        """Set vertical oscillation on/off."""
        return self.set_property("vertical_swing", oscillate)

    def set_vertical_angle(self, angle: int):
        """Set the vertical oscillation angle."""
        if angle not in [30, 60, 90]:
            raise FanException(
                "Unsupported angle. Supported values: "
                + ", ".join(str(i) for i in [30, 60, 90])
            )
        return self.set_property("vertical_swing_angle", angle)

    def set_buzzer(self, buzzer: bool):
        """Set buzzer on/off."""
        if buzzer:
            return self.set_property("buzzer", True)
        else:
            return self.set_property("buzzer", False)

    def set_child_lock(self, lock: bool):
        """Set child lock on/off."""
        return self.set_property("child_lock", lock)

    def set_light(self, light: bool):
        """Set indicator state."""
        return self.set_property("led", light)

    def set_mode(self, mode: OperationModeFanP28):
        """Set mode."""
        return self.set_property("mode", mode.value)

    def delay_off(self, minutes: int):
        """Set delay off in minutes (0-720)."""
        if minutes < 0 or minutes > 720:
            raise FanException(f"Invalid value for a delayed turn off: {minutes}")
        return self.set_property("delay_time", minutes)
