"""MIoT client and status classes for the P43 fan.

Moved out of fan.py unchanged (Phase 6). Derived from
https://github.com/syssi/xiaomi_fan (Apache License 2.0); see NOTICE.
"""

from __future__ import annotations

from miio.fan_common import FanException

from ..const import MODEL_FAN_P43
from .p70 import FanP70, FanStatusP70


class FanStatusP43(FanStatusP70):
    """Container for status reports for FanP43."""


class FanP43(FanP70):
    """Main class representing the Xiaomi Fan P43 (xiaomi.fan.p43)."""

    mapping = {
        # urn:miot-spec-v2:device:fan:0000A005:xiaomi-p43:1
        "power": {"siid": 2, "piid": 1},
        "mode": {"siid": 2, "piid": 3},
        "fan_level": {"siid": 2, "piid": 2},
        "horizontal_swing": {"siid": 2, "piid": 4},
        "horizontal_swing_angle": {"siid": 2, "piid": 5},
        "led": {"siid": 4, "piid": 1},
        "buzzer": {"siid": 5, "piid": 1},
        "child_lock": {"siid": 6, "piid": 1},
        "delay": {"siid": 3, "piid": 1},
        "delay_time": {"siid": 3, "piid": 2},
        "delay_remain_time": {"siid": 3, "piid": 3},
        "fan_speed": {"siid": 2, "piid": 6},
        "toggle": {"siid": 2, "aiid": 1},
        "turn_left": {"siid": 2, "aiid": 2},
        "turn_right": {"siid": 2, "aiid": 3},
    }

    def __init__(
        self,
        ip: str | None = None,
        token: str | None = None,
        start_id: int = 0,
        debug: int = 0,
        lazy_discover: bool = True,
        timeout: int = 5,
        model: str = MODEL_FAN_P43,
    ) -> None:
        """Initialize."""
        super().__init__(
            ip, token, start_id, debug, lazy_discover, timeout, model=model
        )

    def status(self):
        """Retrieve properties."""
        return FanStatusP43(
            {
                prop["did"]: prop["value"] if prop["code"] == 0 else None
                for prop in self.get_properties_for_mapping()
            }
        )

    def set_fan_level(self, fan_level: int):
        """Set fan level (1-4)."""
        if fan_level not in [1, 2, 3, 4]:
            raise FanException(f"Invalid fan level: {fan_level}")
        return self.set_property("fan_level", fan_level)

    def set_angle(self, angle: int):
        """Set the horizontal oscillation angle."""
        if angle not in [30, 60, 90]:
            raise FanException(
                "Unsupported angle. Supported values: "
                + ", ".join(str(i) for i in [30, 60, 90])
            )
        return self.set_property("horizontal_swing_angle", angle)

    def turn(self, direction: str):
        """Turn to the given direction."""
        if direction == "left":
            return self.call_action("turn_left")
        elif direction == "right":
            return self.call_action("turn_right")
        else:
            raise FanException("Unsupported direction. Supported values: left, right")
