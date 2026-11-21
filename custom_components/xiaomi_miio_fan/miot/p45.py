"""MIoT client and status classes for the P45 fan.

Moved out of fan.py unchanged (Phase 6). Derived from
https://github.com/syssi/xiaomi_fan (Apache License 2.0); see NOTICE.
"""

from __future__ import annotations

from enum import Enum

from miio.fan_common import FanException
from miio.miot_device import DeviceStatus, MiotDevice

from ..const import MODEL_FAN_P45
from ._common import filter_request_fields


class OperationModeFanP45(Enum):
    """Operating modes for the Xiaomi Smart Tower Fan 2 (xiaomi.fan.p45)."""

    Straight = 0
    Natural = 1
    Sleep = 2


class FanStatusP45(DeviceStatus):
    """Container for status reports for FanP45 (Xiaomi Smart Tower Fan 2)."""

    def __init__(self, data):
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
    def fan_level(self) -> int:
        """4-step preset level (1..4)."""
        return self.data["fan_level"]

    @property
    def fan_speed(self) -> int:
        """Fine-grained fan speed percentage (1..100)."""
        return self.data["fan_speed"]

    @property
    def mode(self) -> str:
        """Return the operation mode."""
        return OperationModeFanP45(self.data["mode"]).name

    @property
    def horizontal_swing(self) -> bool:
        """Return the horizontal swing state."""
        return self.data["horizontal_swing"]

    @property
    def horizontal_swing_angle(self) -> int:
        """Return the horizontal swing angle."""
        return self.data["horizontal_swing_angle"]

    @property
    def child_lock(self) -> bool:
        """Return the child lock state."""
        return self.data["child_lock"]

    @property
    def led(self) -> bool:
        """Return the LED state."""
        return self.data["led"]

    @property
    def buzzer(self) -> bool:
        """Return the buzzer state."""
        return self.data["buzzer"]

    @property
    def delay(self) -> bool:
        """Return the delay state."""
        return self.data["delay"]

    @property
    def delay_time(self) -> int:
        """Configured off-delay in minutes (0..480)."""
        return self.data["delay_time"]

    @property
    def delay_remain_time(self) -> int:
        """Remaining off-delay countdown in seconds."""
        return self.data["delay_remain_time"]


class FanP45(MiotDevice):
    """Xiaomi Smart Tower Fan 2 (xiaomi.fan.p45, BHR8846EU).

    Implemented against the canonical xiaomi.fan.p45 MIoT spec instance
    urn:miot-spec-v2:device:fan:0000A005:xiaomi-p45:1:0000D062 (the bare
    ``:1`` URN is not registered on miot-spec.org; only the full instance
    with the ``:0000D062`` suffix resolves). The CN counterpart reports as
    dmaker.fan.p45 and uses a different profile, so this class is
    intentionally only registered for the xiaomi.fan.p45 model string.

    The spec exposes all five horizontal swing angles (30/60/90/120/150)
    and three modes (Straight / Natural / Sleep).
    """

    mapping = {
        # urn:miot-spec-v2:device:fan:0000A005:xiaomi-p45:1:0000D062
        "power": {"siid": 2, "piid": 1},
        "fault": {"siid": 2, "piid": 2, "access": ["read"]},
        "mode": {"siid": 2, "piid": 3},
        "fan_level": {"siid": 2, "piid": 4},
        "fan_speed": {"siid": 2, "piid": 5},
        "horizontal_swing": {"siid": 2, "piid": 6},
        "horizontal_swing_angle": {"siid": 2, "piid": 7},
        "led": {"siid": 5, "piid": 1},
        "buzzer": {"siid": 7, "piid": 1},
        "child_lock": {"siid": 11, "piid": 1},
        "delay": {"siid": 12, "piid": 1},
        "delay_time": {"siid": 12, "piid": 2},
        "delay_remain_time": {"siid": 12, "piid": 3},
        "turn_left": {"siid": 2, "aiid": 4},
        "turn_right": {"siid": 2, "aiid": 5},
    }

    def __init__(
        self,
        ip=None,
        token=None,
        start_id=0,
        debug=0,
        lazy_discover=True,
        timeout=5,
        model=MODEL_FAN_P45,
    ):
        """Initialize."""
        super().__init__(
            ip, token, start_id, debug, lazy_discover, timeout, model=model
        )

    def get_properties_for_mapping(self, *, max_properties=15):
        """Retrieve raw properties, skipping action-only entries."""
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
        return FanStatusP45(
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
        """Set fan speed percentage (1..100)."""
        if speed < 1 or speed > 100:
            raise FanException(f"Invalid speed: {speed}")
        return self.set_property("fan_speed", speed)

    def set_fan_level(self, fan_level: int):
        """Set preset fan level (1..4)."""
        if fan_level < 1 or fan_level > 4:
            raise FanException(f"Invalid fan level: {fan_level}")
        return self.set_property("fan_level", fan_level)

    def set_oscillate(self, oscillate: bool):
        """Set horizontal oscillation on/off."""
        return self.set_property("horizontal_swing", bool(oscillate))

    def set_angle(self, angle: int):
        """Set horizontal oscillation included angle.

        Canonical xiaomi.fan.p45 spec exposes 30/60/90/120/150 degrees.
        Region-locked firmware may reject some values at runtime.
        """
        if angle not in [30, 60, 90, 120, 150]:
            raise FanException(
                "Unsupported angle. Supported values: "
                + ", ".join(str(i) for i in [30, 60, 90, 120, 150])
            )
        return self.set_property("horizontal_swing_angle", angle)

    def set_mode(self, mode: OperationModeFanP45):
        """Set mode."""
        return self.set_property("mode", OperationModeFanP45[mode.name].value)

    def set_child_lock(self, lock: bool):
        """Set child lock on/off."""
        return self.set_property("child_lock", bool(lock))

    def set_buzzer(self, buzzer: bool):
        """Set buzzer on/off."""
        return self.set_property("buzzer", bool(buzzer))

    def set_light(self, light: bool):
        """Set indicator state."""
        return self.set_property("led", bool(light))

    def set_led(self, led: bool):
        """Set indicator state through the common fan LED interface."""
        return self.set_light(led)

    def delay_off(self, minutes: int):
        """Set delayed turn-off in minutes (0..480; 0 disables)."""
        if minutes < 0 or minutes > 480:
            raise FanException(f"Invalid value for a delayed turn off: {minutes}")
        # Toggle the delay enable flag in sync with the time value.
        if minutes == 0:
            self.set_property("delay", False)
        else:
            self.set_property("delay", True)
        return self.set_property("delay_time", minutes)

    def turn(self, direction: str):
        """Step the fan 7.5 degrees to the given direction (action call)."""
        if direction == "left":
            return self.call_action("turn_left")
        elif direction == "right":
            return self.call_action("turn_right")
        else:
            raise FanException(
                "Unsupported direction. Supported values: "
                + ", ".join(["left", "right"])
            )
