"""MIoT client and status classes for the P51 fan.

Moved out of fan.py unchanged (Phase 6). Derived from
https://github.com/syssi/xiaomi_fan (Apache License 2.0); see NOTICE.
"""

from __future__ import annotations

from miio.fan_common import FanException

from ..const import MODEL_FAN_P51
from .p70 import FanP70, FanStatusP70


class FanStatusP51(FanStatusP70):
    """Container for status reports for FanP51."""


class FanP51(FanP70):
    """Main class representing the Xiaomi Fan P51 (xiaomi.fan.p51)."""

    mapping = {
        # urn:miot-spec-v2:device:fan:0000A005:xiaomi-p51:1
        "power": {"siid": 2, "piid": 1},
        "fan_level": {"siid": 2, "piid": 2},
        "mode": {"siid": 2, "piid": 3},
        "horizontal_swing": {"siid": 2, "piid": 4},
        "horizontal_swing_angle": {"siid": 2, "piid": 5},
        "fan_speed": {"siid": 2, "piid": 6},
        "led": {"siid": 5, "piid": 1},
        "buzzer": {"siid": 6, "piid": 1},
        "child_lock": {"siid": 7, "piid": 1},
        "delay": {"siid": 9, "piid": 1},
        "delay_time": {"siid": 9, "piid": 2},
        "delay_remain_time": {"siid": 9, "piid": 3},
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
        model: str = MODEL_FAN_P51,
    ) -> None:
        """Initialize."""
        super().__init__(
            ip, token, start_id, debug, lazy_discover, timeout, model=model
        )

    def status(self):
        """Retrieve properties."""
        return FanStatusP51(
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

    def turn(self, direction: str):
        """Turn to the given direction."""
        if direction == "left":
            return self.call_action("turn_left")
        elif direction == "right":
            return self.call_action("turn_right")
        else:
            raise FanException("Unsupported direction. Supported values: left, right")
