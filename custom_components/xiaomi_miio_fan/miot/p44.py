"""MIoT client and status classes for the P44 fan.

Moved out of fan.py unchanged (Phase 6). Derived from
https://github.com/syssi/xiaomi_fan (Apache License 2.0); see NOTICE.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from miio.fan_common import FanException
from miio.miot_device import DeviceStatus, MiotDevice

from ..const import MODEL_FAN_P44
from ._common import filter_request_fields


class OperationModeFanP44(Enum):
    """Operation mode enum for FanP44 (Mijia Smart Evaporative Cooling Fan)."""

    Straight = 0
    Natural = 1
    Sleep = 2
    Cold = 3


class FaultFanP44(Enum):
    """Fault codes reported by FanP44 (Mijia Smart Evaporative Cooling Fan)."""

    NoFault = 0
    LackWater = 1
    NoConnect = 2


class FanStatusP44(DeviceStatus):
    """Container for status reports for FanP44."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize."""
        self.data = data

    @property
    def power(self) -> bool:
        """Return the power state."""
        return self.data["power"]

    @property
    def fault(self) -> int:
        """Return the fault code (0=No Fault, 1=Lack Water, 2=No Connect)."""
        return self.data["fault"]

    @property
    def error_detected(self) -> bool:
        """Return True if the device reports a fault."""
        return self.data["fault"] != FaultFanP44.NoFault.value

    @property
    def water_tank_empty(self) -> bool:
        """Return True if the device reports a lack of water."""
        return self.data["fault"] == FaultFanP44.LackWater.value

    @property
    def mode(self) -> str:
        """Return the operation mode."""
        return OperationModeFanP44(self.data["mode"]).name

    @property
    def fan_level(self) -> int:
        """Return the fan level (1-4)."""
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
        """Return the delay time in minutes."""
        return self.data["delay_time"]

    @property
    def air_cooler(self) -> bool:
        """Return the evaporative water cooling state."""
        return self.data["air_cooler"]


class FanP44(MiotDevice):
    """Representing of a Mijia Smart Evaporative Cooling Fan (dmaker.fan.p44)."""

    mapping = {
        # urn:miot-spec-v2:device:fan:0000A005:dmaker-p44:1
        "power": {"siid": 2, "piid": 1},
        "fan_level": {"siid": 2, "piid": 2},
        "mode": {"siid": 2, "piid": 3},
        "horizontal_swing": {"siid": 2, "piid": 4},
        "air_cooler": {"siid": 2, "piid": 6},
        "fault": {"siid": 2, "piid": 7, "access": ["read"]},
        "led": {"siid": 4, "piid": 1},
        "buzzer": {"siid": 5, "piid": 1},
        "child_lock": {"siid": 7, "piid": 1},
        "delay_time": {"siid": 3, "piid": 1},
    }

    def __init__(
        self,
        ip: str | None = None,
        token: str | None = None,
        start_id: int = 0,
        debug: int = 0,
        lazy_discover: bool = True,
        timeout: int = 5,
        model: str = MODEL_FAN_P44,
    ) -> None:
        """Initialize."""
        super().__init__(
            ip, token, start_id, debug, lazy_discover, timeout, model=model
        )

    def get_properties_for_mapping(self, *, max_properties=15) -> list:
        """Retrieve raw properties."""
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
        return FanStatusP44(
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

    def set_fan_level(self, fan_level: int):
        """Set fan level (1-4)."""
        if fan_level not in [1, 2, 3, 4]:
            raise FanException(f"Invalid fan level: {fan_level}")
        return self.set_property("fan_level", fan_level)

    def set_oscillate(self, oscillate: bool):
        """Set horizontal oscillation on/off."""
        return self.set_property("horizontal_swing", bool(oscillate))

    def set_mode(self, mode: OperationModeFanP44):
        """Set mode."""
        return self.set_property("mode", mode.value)

    def set_child_lock(self, lock: bool):
        """Set child lock on/off."""
        return self.set_property("child_lock", bool(lock))

    def set_buzzer(self, buzzer: bool):
        """Set buzzer on/off."""
        return self.set_property("buzzer", bool(buzzer))

    def set_light(self, light: bool):
        """Set indicator state."""
        return self.set_property("led", bool(light))

    def set_air_cooler(self, air_cooler: bool):
        """Set the evaporative water cooling on/off."""
        return self.set_property("air_cooler", bool(air_cooler))

    def delay_off(self, minutes: int):
        """Set delay off in minutes (0-480). 0 deactivates the timer."""
        if minutes < 0 or minutes > 480:
            raise FanException(f"Invalid value for a delayed turn off: {minutes}")
        return self.set_property("delay_time", minutes)
