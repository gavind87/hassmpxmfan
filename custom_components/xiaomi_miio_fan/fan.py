"""Fan platform for Xiaomi and Mijia smart fans.

Derived from https://github.com/syssi/xiaomi_fan (Apache License 2.0,
original work by Sebastian Muszynski). Modified by gavind87: config flow,
device registry, coordinator/auto-heal integration and other changes.
See the NOTICE file in the repository root.
"""

import asyncio
from enum import Enum
from functools import partial
import math
import time
from typing import Any

from homeassistant import config_entries
from homeassistant.components.fan import PLATFORM_SCHEMA, FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    CONF_HOST,
    CONF_NAME,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from miio import DeviceException, Fan, Fan1C, FanLeshow, FanMiot, FanP5
from miio.fan_common import FanException
from miio.fan_common import LedBrightness as FanLedBrightness
from miio.fan_common import MoveDirection as FanMoveDirection
from miio.fan_common import OperationMode as FanOperationMode
from miio.integrations.fan.leshow.fan_leshow import (
    OperationMode as FanLeshowOperationMode,
)
import voluptuous as vol

from .const import (
    CONF_MODEL,
    CONF_PRESET_MODES_OVERRIDE,
    CONF_RETRIES,
    DATA_KEY,
    DATA_SERVICES_REGISTERED,
    DEFAULT_NAME,
    DEFAULT_RETRIES,
    DOMAIN,
    MODEL_FAN_1C,
    MODEL_FAN_2LITE,
    MODEL_FAN_LESHOW_SS4,
    MODEL_FAN_LESHOW_SS310,
    MODEL_FAN_P5,
    MODEL_FAN_P8,
    MODEL_FAN_P9,
    MODEL_FAN_P10,
    MODEL_FAN_P11,
    MODEL_FAN_P15,
    MODEL_FAN_P18,
    MODEL_FAN_P28,
    MODEL_FAN_P30,
    MODEL_FAN_P33,
    MODEL_FAN_P39,
    MODEL_FAN_P43,
    MODEL_FAN_P44,
    MODEL_FAN_P45,
    MODEL_FAN_P51,
    MODEL_FAN_P70,
    MODEL_FAN_P76,
    MODEL_FAN_P85,
    MODEL_FAN_SA1,
    MODEL_FAN_V2,
    MODEL_FAN_V3,
    MODEL_FAN_XIAOMI_P30,
    MODEL_FAN_ZA1,
    MODEL_FAN_ZA3,
    MODEL_FAN_ZA4,
    MODEL_FAN_ZA5,
    SUPPORTED_MODELS,
)
from .discovery import broadcast_discover_device_ids
from .log import get_logger
from .miot.fan_2lite import FAN_2LITE_SPEED_COUNT, Fan2Lite, OperationModeFan2Lite
from .miot.p28 import FanP28, OperationModeFanP28
from .miot.p33 import FanP33, OperationModeFanP33
from .miot.p39 import FanP39, OperationModeFanP39
from .miot.p43 import FanP43
from .miot.p44 import FanP44, OperationModeFanP44
from .miot.p45 import FanP45, OperationModeFanP45
from .miot.p51 import FanP51
from .miot.p70 import FanP70, OperationModeFanP70
from .miot.p76 import FanP76, OperationModeFanP76
from .miot.p85 import FanP85
from .miot.ss310 import FanSS310, OperationModeFanSS310
from .miot.xiaomi_p30 import FanXiaomiP30, OperationModeFanXiaomiP30
from .miot.za5 import FanZA5

_LOGGER = get_logger(__name__)

# Minimum gap between LAN scans for a fan that stays unreachable.
HEAL_COOLDOWN_SECONDS = 300

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODEL): vol.In(SUPPORTED_MODELS),
        vol.Optional(CONF_RETRIES, default=DEFAULT_RETRIES): cv.positive_int,
        vol.Optional(CONF_PRESET_MODES_OVERRIDE, default=None): vol.Any(
            None, [cv.string]
        ),
    }
)

SPEED_OFF = "off"

ATTR_MODEL = "model"
ATTR_BRIGHTNESS = "brightness"
ATTR_DIRECTION = "direction"

ATTR_TEMPERATURE = "temperature"
ATTR_HUMIDITY = "humidity"
ATTR_LED = "led"
ATTR_LED_BRIGHTNESS = "led_brightness"
ATTR_RAW_LED_BRIGHTNESS = "raw_led_brightness"
ATTR_BUZZER = "buzzer"
ATTR_CHILD_LOCK = "child_lock"
ATTR_NATURAL_SPEED = "natural_speed"
ATTR_OSCILLATE = "oscillate"
ATTR_BATTERY = "battery"
ATTR_BATTERY_CHARGE = "battery_charge"
ATTR_BATTERY_STATE = "battery_state"
ATTR_AC_POWER = "ac_power"
ATTR_DELAY_OFF_COUNTDOWN = "delay_off_countdown"
ATTR_ANGLE = "angle"
ATTR_DIRECT_SPEED = "direct_speed"
ATTR_USE_TIME = "use_time"
ATTR_BUTTON_PRESSED = "button_pressed"
ATTR_RAW_SPEED = "raw_speed"
ATTR_IONIZER = "anion"
ATTR_AIR_COOLER = "air_cooler"
ATTR_WATER_TANK_EMPTY = "water_tank_empty"
ATTR_VERTICAL_OSCILLATE = "vertical_oscillate"
ATTR_VERTICAL_ANGLE = "vertical_angle"

# Fan Leshow SS4
ATTR_ERROR_DETECTED = "error_detected"

AVAILABLE_ATTRIBUTES_FAN = {
    ATTR_ANGLE: "angle",
    ATTR_RAW_SPEED: "speed",
    ATTR_DELAY_OFF_COUNTDOWN: "delay_off_countdown",
    ATTR_AC_POWER: "ac_power",
    ATTR_OSCILLATE: "oscillate",
    ATTR_DIRECT_SPEED: "direct_speed",
    ATTR_NATURAL_SPEED: "natural_speed",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_BUZZER: "buzzer",
    ATTR_LED_BRIGHTNESS: "led_brightness",
    ATTR_USE_TIME: "use_time",
    # Additional properties of version 2 and 3
    ATTR_TEMPERATURE: "temperature",
    ATTR_HUMIDITY: "humidity",
    ATTR_BATTERY: "battery",
    ATTR_BATTERY_CHARGE: "battery_charge",
    ATTR_BUTTON_PRESSED: "button_pressed",
    # Additional properties of version 2
    ATTR_LED: "led",
    ATTR_BATTERY_STATE: "battery_state",
}

AVAILABLE_ATTRIBUTES_FAN_P5 = {
    ATTR_MODE: "mode",
    ATTR_OSCILLATE: "oscillate",
    ATTR_ANGLE: "angle",
    ATTR_DELAY_OFF_COUNTDOWN: "delay_off_countdown",
    ATTR_LED: "led",
    ATTR_BUZZER: "buzzer",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_RAW_SPEED: "speed",
}


AVAILABLE_ATTRIBUTES_FAN_P33 = {
    ATTR_MODE: "mode",
    ATTR_OSCILLATE: "oscillate",
    ATTR_ANGLE: "angle",
    ATTR_DELAY_OFF_COUNTDOWN: "delay_off_countdown",
    ATTR_LED: "led",
    ATTR_BUZZER: "buzzer",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_RAW_SPEED: "speed",
}

AVAILABLE_ATTRIBUTES_FAN_P39 = {
    ATTR_MODE: "mode",
    ATTR_OSCILLATE: "oscillate",
    ATTR_ANGLE: "angle",
    ATTR_DELAY_OFF_COUNTDOWN: "delay_off_countdown",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_RAW_SPEED: "speed",
}

AVAILABLE_ATTRIBUTES_FAN_P45 = {
    ATTR_MODE: "mode",
    ATTR_OSCILLATE: "horizontal_swing",
    ATTR_ANGLE: "horizontal_swing_angle",
    ATTR_DELAY_OFF_COUNTDOWN: "delay_time",
    ATTR_LED: "led",
    ATTR_BUZZER: "buzzer",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_RAW_SPEED: "fan_speed",
}

AVAILABLE_ATTRIBUTES_FAN_XIAOMI_P30 = {
    ATTR_MODE: "mode",
    ATTR_OSCILLATE: "horizontal_swing",
    ATTR_ANGLE: "horizontal_swing_angle",
    ATTR_DELAY_OFF_COUNTDOWN: "delay_time",
    ATTR_LED: "led",
    ATTR_BUZZER: "buzzer",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_RAW_SPEED: "fan_speed",
}

AVAILABLE_ATTRIBUTES_FAN_P76 = {
    ATTR_MODE: "mode",
    ATTR_OSCILLATE: "horizontal_swing",
    ATTR_ANGLE: "horizontal_swing_angle",
    ATTR_VERTICAL_OSCILLATE: "vertical_swing",
    ATTR_VERTICAL_ANGLE: "vertical_swing_angle",
    ATTR_DELAY_OFF_COUNTDOWN: "delay_time",
    ATTR_LED: "led",
    ATTR_BUZZER: "buzzer",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_RAW_SPEED: "fan_speed",
}

AVAILABLE_ATTRIBUTES_FAN_P70 = {
    ATTR_MODE: "mode",
    ATTR_OSCILLATE: "horizontal_swing",
    ATTR_ANGLE: "horizontal_swing_angle",
    ATTR_VERTICAL_OSCILLATE: "vertical_swing",
    ATTR_VERTICAL_ANGLE: "vertical_swing_angle",
    ATTR_DELAY_OFF_COUNTDOWN: "delay_time",
    ATTR_LED: "led",
    ATTR_BUZZER: "buzzer",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_RAW_SPEED: "fan_speed",
}

AVAILABLE_ATTRIBUTES_FAN_2LITE = {
    ATTR_MODE: "mode",
    ATTR_OSCILLATE: "horizontal_swing",
    ATTR_DELAY_OFF_COUNTDOWN: "delay_time",
    ATTR_LED: "led",
    ATTR_BUZZER: "buzzer",
    ATTR_CHILD_LOCK: "child_lock",
}

AVAILABLE_ATTRIBUTES_FAN_P85 = {
    ATTR_MODE: "mode",
    ATTR_OSCILLATE: "horizontal_swing",
    ATTR_ANGLE: "horizontal_swing_angle",
    ATTR_DELAY_OFF_COUNTDOWN: "delay_time",
    ATTR_LED: "led",
    ATTR_BUZZER: "buzzer",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_RAW_SPEED: "fan_speed",
}

AVAILABLE_ATTRIBUTES_FAN_P43 = {
    ATTR_MODE: "mode",
    ATTR_OSCILLATE: "horizontal_swing",
    ATTR_ANGLE: "horizontal_swing_angle",
    ATTR_DELAY_OFF_COUNTDOWN: "delay_time",
    ATTR_LED: "led",
    ATTR_BUZZER: "buzzer",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_RAW_SPEED: "fan_speed",
}

AVAILABLE_ATTRIBUTES_FAN_P44 = {
    ATTR_MODE: "mode",
    ATTR_OSCILLATE: "horizontal_swing",
    ATTR_DELAY_OFF_COUNTDOWN: "delay_time",
    ATTR_LED: "led",
    ATTR_BUZZER: "buzzer",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_RAW_SPEED: "fan_level",
    ATTR_AIR_COOLER: "air_cooler",
    ATTR_ERROR_DETECTED: "error_detected",
    ATTR_WATER_TANK_EMPTY: "water_tank_empty",
}

AVAILABLE_ATTRIBUTES_FAN_P51 = {
    ATTR_MODE: "mode",
    ATTR_OSCILLATE: "horizontal_swing",
    ATTR_ANGLE: "horizontal_swing_angle",
    ATTR_DELAY_OFF_COUNTDOWN: "delay_time",
    ATTR_LED: "led",
    ATTR_BUZZER: "buzzer",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_RAW_SPEED: "fan_speed",
}

AVAILABLE_ATTRIBUTES_FAN_P28 = {
    ATTR_MODE: "mode",
    ATTR_OSCILLATE: "horizontal_swing",
    ATTR_ANGLE: "horizontal_swing_angle",
    ATTR_VERTICAL_OSCILLATE: "vertical_swing",
    ATTR_VERTICAL_ANGLE: "vertical_swing_angle",
    ATTR_DELAY_OFF_COUNTDOWN: "delay_time",
    ATTR_LED: "led",
    ATTR_BUZZER: "buzzer",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_RAW_SPEED: "speed",
    ATTR_TEMPERATURE: "temperature",
    ATTR_HUMIDITY: "humidity",
}

AVAILABLE_ATTRIBUTES_FAN_LESHOW_SS4 = {
    ATTR_MODE: "mode",
    ATTR_RAW_SPEED: "speed",
    ATTR_BUZZER: "buzzer",
    ATTR_OSCILLATE: "oscillate",
    ATTR_DELAY_OFF_COUNTDOWN: "delay_off_countdown",
    ATTR_ERROR_DETECTED: "error_detected",
}

AVAILABLE_ATTRIBUTES_FAN_LESHOW_SS310 = {
    ATTR_MODE: "mode",
    ATTR_OSCILLATE: "horizontal_swing",
    ATTR_VERTICAL_OSCILLATE: "vertical_swing",
    ATTR_RAW_SPEED: "fan_level",
}

AVAILABLE_ATTRIBUTES_FAN_1C = {
    ATTR_MODE: "mode",
    ATTR_RAW_SPEED: "speed",
    ATTR_BUZZER: "buzzer",
    ATTR_OSCILLATE: "oscillate",
    ATTR_DELAY_OFF_COUNTDOWN: "delay_off_countdown",
    ATTR_LED: "led",
    ATTR_CHILD_LOCK: "child_lock",
}

AVAILABLE_ATTRIBUTES_FAN_ZA5 = {
    ATTR_ANGLE: "swing_mode_angle",
    ATTR_DIRECT_SPEED: "fan_speed",
    ATTR_NATURAL_SPEED: "fan_speed",
    ATTR_DELAY_OFF_COUNTDOWN: "power_off_time",
    ATTR_AC_POWER: "powersupply_attached",
    ATTR_OSCILLATE: "swing_mode",
    ATTR_MODE: "mode",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_BUZZER: "buzzer",
    ATTR_RAW_LED_BRIGHTNESS: "light",
    ATTR_LED_BRIGHTNESS: "light_enum",
    ATTR_TEMPERATURE: "temperature",
    ATTR_HUMIDITY: "humidity",
    ATTR_BUTTON_PRESSED: "buttons_pressed",
    # Fixed attributes
    ATTR_LED: "led",
    ATTR_RAW_SPEED: "speed_rpm",
    ATTR_BATTERY: "battery_supported",
    ATTR_BATTERY_STATE: "battery_state",
    ATTR_IONIZER: "anion",
}

FAN_SPEED_LEVEL1 = "Level 1"
FAN_SPEED_LEVEL2 = "Level 2"
FAN_SPEED_LEVEL3 = "Level 3"
FAN_SPEED_LEVEL4 = "Level 4"
FAN_SPEED_LEVEL5 = "Level 5"

FAN_SPEED_NATURAL1 = "Natural 1"
FAN_SPEED_NATURAL2 = "Natural 2"
FAN_SPEED_NATURAL3 = "Natural 3"
FAN_SPEED_NATURAL4 = "Natural 4"

FAN_PRESET_MODES = {
    SPEED_OFF: range(0, 1),
    FAN_SPEED_LEVEL1: range(1, 26),
    FAN_SPEED_LEVEL2: range(26, 51),
    FAN_SPEED_LEVEL3: range(51, 76),
    FAN_SPEED_LEVEL4: range(76, 101),
}

FAN_PRESET_MODE_VALUES = {
    SPEED_OFF: 0,
    FAN_SPEED_LEVEL1: 1,
    FAN_SPEED_LEVEL2: 35,
    FAN_SPEED_LEVEL3: 74,
    FAN_SPEED_LEVEL4: 100,
}

FAN_PRESET_MODE_VALUES_P5 = {
    SPEED_OFF: 0,
    FAN_SPEED_LEVEL1: 1,
    FAN_SPEED_LEVEL2: 35,
    FAN_SPEED_LEVEL3: 70,
    FAN_SPEED_LEVEL4: 100,
}

FAN_PRESET_MODES_1C = {
    SPEED_OFF: 0,
    FAN_SPEED_LEVEL1: 1,
    FAN_SPEED_LEVEL2: 2,
    FAN_SPEED_LEVEL3: 3,
}

FAN_PRESET_MODES_ZA5 = {
    SPEED_OFF: 0,
    FAN_SPEED_LEVEL1: 25,
    FAN_SPEED_LEVEL2: 50,
    FAN_SPEED_LEVEL3: 75,
    FAN_SPEED_LEVEL4: 100,
}

FAN_PRESET_MODES_P33 = {
    SPEED_OFF: 0,
    FAN_SPEED_LEVEL1: 1,
    FAN_SPEED_LEVEL2: 35,
    FAN_SPEED_LEVEL3: 70,
    FAN_SPEED_LEVEL4: 100,
}

FAN_PRESET_MODES_P39 = {
    SPEED_OFF: 0,
    FAN_SPEED_LEVEL1: 1,
    FAN_SPEED_LEVEL2: 35,
    FAN_SPEED_LEVEL3: 70,
    FAN_SPEED_LEVEL4: 100,
}

FAN_SPEEDS_1C = list(FAN_PRESET_MODES_1C)
FAN_SPEEDS_1C.remove(SPEED_OFF)

FAN_PRESET_MODES_P76 = {
    SPEED_OFF: -1,
    FAN_SPEED_LEVEL1: 0,
    FAN_SPEED_LEVEL2: 1,
    FAN_SPEED_LEVEL3: 2,
    FAN_SPEED_LEVEL4: 3,
    FAN_SPEED_NATURAL1: 0,
    FAN_SPEED_NATURAL2: 1,
    FAN_SPEED_NATURAL3: 2,
    FAN_SPEED_NATURAL4: 3,
}

FAN_PRESET_MODES_XIAOMI_P30 = {
    SPEED_OFF: -1,
    FAN_SPEED_LEVEL1: 1,
    FAN_SPEED_LEVEL2: 2,
    FAN_SPEED_LEVEL3: 3,
    FAN_SPEED_LEVEL4: 4,
    FAN_SPEED_NATURAL1: 1,
    FAN_SPEED_NATURAL2: 2,
    FAN_SPEED_NATURAL3: 3,
    FAN_SPEED_NATURAL4: 4,
}

FAN_PRESET_MODES_P70 = {
    SPEED_OFF: -1,
    FAN_SPEED_LEVEL1: 0,
    FAN_SPEED_LEVEL2: 1,
    FAN_SPEED_LEVEL3: 2,
    FAN_SPEED_LEVEL4: 3,
}

FAN_PRESET_MODES_P85 = {
    SPEED_OFF: -1,
    FAN_SPEED_LEVEL1: 1,
    FAN_SPEED_LEVEL2: 2,
    FAN_SPEED_LEVEL3: 3,
    FAN_SPEED_LEVEL4: 4,
    FAN_SPEED_NATURAL1: 1,
    FAN_SPEED_NATURAL2: 2,
    FAN_SPEED_NATURAL3: 3,
    FAN_SPEED_NATURAL4: 4,
}

FAN_PRESET_MODES_P43 = {
    SPEED_OFF: -1,
    FAN_SPEED_LEVEL1: 1,
    FAN_SPEED_LEVEL2: 2,
    FAN_SPEED_LEVEL3: 3,
    FAN_SPEED_LEVEL4: 4,
    FAN_SPEED_NATURAL1: 1,
    FAN_SPEED_NATURAL2: 2,
    FAN_SPEED_NATURAL3: 3,
    FAN_SPEED_NATURAL4: 4,
}

FAN_PRESET_MODE_SLEEP = "Sleep"

# Smart Tower Fan 2 (xiaomi.fan.p45) — fan-level enum: Level1..Level4 (1..4).
# Sleep is a standalone mode (no level selector) and is treated as a single
# preset that maps to mode=Sleep.
FAN_PRESET_MODES_P45 = {
    SPEED_OFF: -1,
    FAN_SPEED_LEVEL1: 1,
    FAN_SPEED_LEVEL2: 2,
    FAN_SPEED_LEVEL3: 3,
    FAN_SPEED_LEVEL4: 4,
    FAN_SPEED_NATURAL1: 1,
    FAN_SPEED_NATURAL2: 2,
    FAN_SPEED_NATURAL3: 3,
    FAN_SPEED_NATURAL4: 4,
    FAN_PRESET_MODE_SLEEP: 1,
}

FAN_PRESET_MODES_2LITE = [FAN_PRESET_MODE_SLEEP]


FAN_PRESET_MODE_COLD_AIR = "ColdAir"

FAN_PRESET_MODES_P44 = {
    SPEED_OFF: -1,
    FAN_SPEED_LEVEL1: 1,
    FAN_SPEED_LEVEL2: 2,
    FAN_SPEED_LEVEL3: 3,
    FAN_SPEED_LEVEL4: 4,
    FAN_SPEED_NATURAL1: 1,
    FAN_SPEED_NATURAL2: 2,
    FAN_SPEED_NATURAL3: 3,
    FAN_SPEED_NATURAL4: 4,
    FAN_PRESET_MODE_SLEEP: 1,
    FAN_PRESET_MODE_COLD_AIR: 1,
}

FAN_P44_SPEED_COUNT = 4

FAN_PRESET_MODES_P51 = {
    SPEED_OFF: -1,
    FAN_SPEED_LEVEL1: 1,
    FAN_SPEED_LEVEL2: 2,
    FAN_SPEED_LEVEL3: 3,
    FAN_SPEED_LEVEL4: 4,
    FAN_SPEED_NATURAL1: 1,
    FAN_SPEED_NATURAL2: 2,
    FAN_SPEED_NATURAL3: 3,
    FAN_SPEED_NATURAL4: 4,
}

# Raw fan_level values of the leshow.fan.ss310 MIoT spec
FAN_LEVELS_SS310 = {
    FAN_SPEED_LEVEL1: 1,
    FAN_SPEED_LEVEL2: 25,
    FAN_SPEED_LEVEL3: 50,
    FAN_SPEED_LEVEL4: 75,
    FAN_SPEED_LEVEL5: 100,
}

FAN_SPEEDS_SS310 = list(FAN_LEVELS_SS310)

FAN_PRESET_MODES_P28 = {
    SPEED_OFF: -1,
    FAN_SPEED_LEVEL1: 1,
    FAN_SPEED_LEVEL2: 2,
    FAN_SPEED_LEVEL3: 3,
    FAN_SPEED_LEVEL4: 4,
    FAN_SPEED_NATURAL1: 1,
    FAN_SPEED_NATURAL2: 2,
    FAN_SPEED_NATURAL3: 3,
    FAN_SPEED_NATURAL4: 4,
    FAN_PRESET_MODE_SLEEP: 1,
}

SUCCESS = ["ok"]

FEATURE_SET_BUZZER = 1
FEATURE_SET_LED = 2
FEATURE_SET_CHILD_LOCK = 4
FEATURE_SET_LED_BRIGHTNESS = 8
FEATURE_SET_OSCILLATION_ANGLE = 16
FEATURE_SET_NATURAL_MODE = 32
FEATURE_SET_ANION = 64
FEATURE_SET_VERTICAL_OSCILLATION = 128
FEATURE_TURN = 256
FEATURE_SET_VERTICAL_OSCILLATION_ANGLE = 512
FEATURE_SET_AIR_COOLER = 1024

FEATURE_FLAGS_FAN = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED_BRIGHTNESS
    | FEATURE_SET_OSCILLATION_ANGLE
    | FEATURE_SET_NATURAL_MODE
)

FEATURE_FLAGS_FAN_P5 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_NATURAL_MODE
    | FEATURE_SET_OSCILLATION_ANGLE
    | FEATURE_SET_LED
)

FEATURE_FLAGS_FAN_LESHOW_SS4 = FEATURE_SET_BUZZER
FEATURE_FLAGS_FAN_LESHOW_SS310 = FEATURE_SET_VERTICAL_OSCILLATION
FEATURE_FLAGS_FAN_1C = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_OSCILLATION_ANGLE
    | FEATURE_SET_NATURAL_MODE
)

FEATURE_FLAGS_FAN_ZA5 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED_BRIGHTNESS
    | FEATURE_SET_OSCILLATION_ANGLE
    | FEATURE_SET_NATURAL_MODE
    | FEATURE_SET_ANION
)

FEATURE_FLAGS_FAN_P33 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_OSCILLATION_ANGLE
    | FEATURE_SET_NATURAL_MODE
)

FEATURE_FLAGS_FAN_P39 = (
    FEATURE_SET_CHILD_LOCK | FEATURE_SET_OSCILLATION_ANGLE | FEATURE_SET_NATURAL_MODE
)

# Xiaomi Smart Tower Fan 2 (xiaomi.fan.p45). Canonical spec exposes
# 30/60/90/120/150 swing angles and three modes (Straight / Natural / Sleep).
FEATURE_FLAGS_FAN_P45 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_OSCILLATION_ANGLE
    | FEATURE_SET_NATURAL_MODE
    | FEATURE_TURN
)

FEATURE_FLAGS_FAN_XIAOMI_P30 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_OSCILLATION_ANGLE
    | FEATURE_SET_NATURAL_MODE
    | FEATURE_TURN
)

FEATURE_FLAGS_FAN_P76 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_OSCILLATION_ANGLE
    | FEATURE_SET_NATURAL_MODE
    | FEATURE_SET_VERTICAL_OSCILLATION
    | FEATURE_TURN
    | FEATURE_SET_VERTICAL_OSCILLATION_ANGLE
)

FEATURE_FLAGS_FAN_P70 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_OSCILLATION_ANGLE
    | FEATURE_SET_NATURAL_MODE
    | FEATURE_SET_VERTICAL_OSCILLATION
    | FEATURE_TURN
    | FEATURE_SET_VERTICAL_OSCILLATION_ANGLE
)

FEATURE_FLAGS_FAN_2LITE = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_NATURAL_MODE
)

FEATURE_FLAGS_FAN_P85 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_OSCILLATION_ANGLE
    | FEATURE_SET_NATURAL_MODE
    | FEATURE_TURN
)

FEATURE_FLAGS_FAN_P43 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_OSCILLATION_ANGLE
    | FEATURE_SET_NATURAL_MODE
    | FEATURE_TURN
)

FEATURE_FLAGS_FAN_P44 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_NATURAL_MODE
    | FEATURE_SET_AIR_COOLER
)

FEATURE_FLAGS_FAN_P51 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_OSCILLATION_ANGLE
    | FEATURE_SET_NATURAL_MODE
    | FEATURE_TURN
)

# fan_turn is deliberately omitted: start-left/right/up/down (dm-service,
# siid 8) are write-only bool properties with unverified movement semantics.
FEATURE_FLAGS_FAN_P28 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_OSCILLATION_ANGLE
    | FEATURE_SET_NATURAL_MODE
    | FEATURE_SET_VERTICAL_OSCILLATION
    | FEATURE_SET_VERTICAL_OSCILLATION_ANGLE
)

SERVICE_SET_BUZZER_ON = "fan_set_buzzer_on"
SERVICE_SET_BUZZER_OFF = "fan_set_buzzer_off"
SERVICE_SET_CHILD_LOCK_ON = "fan_set_child_lock_on"
SERVICE_SET_CHILD_LOCK_OFF = "fan_set_child_lock_off"
SERVICE_SET_LED_BRIGHTNESS = "fan_set_led_brightness"
SERVICE_SET_RAW_LED_BRIGHTNESS = "fan_set_raw_led_brightness"
SERVICE_SET_OSCILLATION_ANGLE = "fan_set_oscillation_angle"
SERVICE_SET_DELAY_OFF = "fan_set_delay_off"
SERVICE_SET_NATURAL_MODE_ON = "fan_set_natural_mode_on"
SERVICE_SET_NATURAL_MODE_OFF = "fan_set_natural_mode_off"
SERVICE_SET_ANION_ON = "fan_set_anion_on"
SERVICE_SET_ANION_OFF = "fan_set_anion_off"
SERVICE_SET_AIR_COOLER_ON = "fan_set_air_cooler_on"
SERVICE_SET_AIR_COOLER_OFF = "fan_set_air_cooler_off"
SERVICE_SET_VERTICAL_OSCILLATION_ON = "fan_set_vertical_oscillation_on"
SERVICE_SET_VERTICAL_OSCILLATION_OFF = "fan_set_vertical_oscillation_off"
SERVICE_TURN = "fan_turn"
SERVICE_SET_VERTICAL_OSCILLATION_ANGLE = "fan_set_vertical_oscillation_angle"

AIRPURIFIER_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})

SERVICE_SCHEMA_LED_BRIGHTNESS = AIRPURIFIER_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_BRIGHTNESS): vol.All(vol.Coerce(int), vol.Range(min=0, max=2))}
)

SERVICE_SCHEMA_RAW_LED_BRIGHTNESS = AIRPURIFIER_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_BRIGHTNESS): vol.All(vol.Coerce(int), vol.Range(min=0, max=100))}
)

SERVICE_SCHEMA_OSCILLATION_ANGLE = AIRPURIFIER_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_ANGLE): cv.positive_int}
)

SERVICE_SCHEMA_DELAY_OFF = AIRPURIFIER_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_DELAY_OFF_COUNTDOWN): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=600)
        )
    }
)

SERVICE_SCHEMA_TURN = AIRPURIFIER_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_DIRECTION): vol.All(
            vol.Coerce(str), vol.In(["left", "right", "up", "down"])
        )
    }
)

SERVICE_SCHEMA_VERTICAL_OSCILLATION_ANGLE = AIRPURIFIER_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_VERTICAL_ANGLE): cv.positive_int}
)

SERVICE_TO_METHOD = {
    SERVICE_SET_BUZZER_ON: {"method": "async_set_buzzer_on"},
    SERVICE_SET_BUZZER_OFF: {"method": "async_set_buzzer_off"},
    SERVICE_SET_CHILD_LOCK_ON: {"method": "async_set_child_lock_on"},
    SERVICE_SET_CHILD_LOCK_OFF: {"method": "async_set_child_lock_off"},
    SERVICE_SET_LED_BRIGHTNESS: {
        "method": "async_set_led_brightness",
        "schema": SERVICE_SCHEMA_LED_BRIGHTNESS,
    },
    SERVICE_SET_RAW_LED_BRIGHTNESS: {
        "method": "async_set_raw_led_brightness",
        "schema": SERVICE_SCHEMA_RAW_LED_BRIGHTNESS,
    },
    SERVICE_SET_OSCILLATION_ANGLE: {
        "method": "async_set_oscillation_angle",
        "schema": SERVICE_SCHEMA_OSCILLATION_ANGLE,
    },
    SERVICE_SET_DELAY_OFF: {
        "method": "async_set_delay_off",
        "schema": SERVICE_SCHEMA_DELAY_OFF,
    },
    SERVICE_SET_NATURAL_MODE_ON: {"method": "async_set_natural_mode_on"},
    SERVICE_SET_NATURAL_MODE_OFF: {"method": "async_set_natural_mode_off"},
    SERVICE_SET_ANION_ON: {"method": "async_set_anion_on"},
    SERVICE_SET_ANION_OFF: {"method": "async_set_anion_off"},
    SERVICE_SET_AIR_COOLER_ON: {"method": "async_set_air_cooler_on"},
    SERVICE_SET_AIR_COOLER_OFF: {"method": "async_set_air_cooler_off"},
    SERVICE_SET_VERTICAL_OSCILLATION_ON: {
        "method": "async_set_vertical_oscillation_on"
    },
    SERVICE_SET_VERTICAL_OSCILLATION_OFF: {
        "method": "async_set_vertical_oscillation_off"
    },
    SERVICE_TURN: {
        "method": "async_turn",
        "schema": SERVICE_SCHEMA_TURN,
    },
    SERVICE_SET_VERTICAL_OSCILLATION_ANGLE: {
        "method": "async_set_vertical_oscillation_angle",
        "schema": SERVICE_SCHEMA_VERTICAL_OSCILLATION_ANGLE,
    },
}


# pylint: disable=unused-argument
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import the YAML-configured miio fan into a config entry.

    This platform no longer creates entities directly. Existing
    `fan: - platform: xiaomi_miio_fan` entries in configuration.yaml are
    imported into a config entry once, which can then also be managed (or
    added from scratch) from Settings > Devices & Services.
    """
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=config,
        )
    )


def _model_spec(  # noqa: PLR0911 - one early return per supported model
    model: str,
) -> tuple[type, str, type] | None:
    """Return (client_cls, client_model, entity_cls) for a model, or None.

    `client_model` is the model string passed to the miio *client*
    constructor, which for a few models is canonicalized to a close relative
    with the same wire protocol (e.g. P18/P30 talk the P10 MIoT spec) - the
    HA entity still displays/stores the real, user-facing `model`.
    """
    if model in [
        MODEL_FAN_V2,
        MODEL_FAN_V3,
        MODEL_FAN_SA1,
        MODEL_FAN_ZA1,
        MODEL_FAN_ZA3,
        MODEL_FAN_ZA4,
    ]:
        return (Fan, model, XiaomiFan)
    if model == MODEL_FAN_P5:
        return (FanP5, model, XiaomiFanP5)
    if model == MODEL_FAN_P9:
        return (FanMiot, model, XiaomiFanMiot)
    if model in [MODEL_FAN_P10, MODEL_FAN_P18, MODEL_FAN_P30]:
        return (FanMiot, MODEL_FAN_P10, XiaomiFanMiot)
    if model == MODEL_FAN_XIAOMI_P30:
        return (FanXiaomiP30, model, XiaomiFanXiaomiP30)
    if model in [MODEL_FAN_P11, MODEL_FAN_P15]:
        return (FanMiot, MODEL_FAN_P11, XiaomiFanMiot)
    if model == MODEL_FAN_LESHOW_SS4:
        return (FanLeshow, model, XiaomiFanLeshow)
    if model == MODEL_FAN_LESHOW_SS310:
        return (FanSS310, model, XiaomiFanLeshowSS310)
    if model in [MODEL_FAN_1C, MODEL_FAN_P8]:
        return (Fan1C, model, XiaomiFan1C)
    if model == MODEL_FAN_ZA5:
        return (FanZA5, model, XiaomiFanZA5)
    if model == MODEL_FAN_P33:
        return (FanP33, model, XiaomiFanP33)
    if model == MODEL_FAN_P39:
        return (FanP39, model, XiaomiFanP39)
    if model == MODEL_FAN_P45:
        return (FanP45, model, XiaomiFanP45)
    if model == MODEL_FAN_P76:
        return (FanP76, model, XiaomiFanP76)
    if model == MODEL_FAN_P70:
        return (FanP70, model, XiaomiFanP70)
    if model == MODEL_FAN_P85:
        return (FanP85, model, XiaomiFanP85)
    if model == MODEL_FAN_P43:
        return (FanP43, model, XiaomiFanP43)
    if model == MODEL_FAN_P44:
        return (FanP44, model, XiaomiFanP44)
    if model == MODEL_FAN_P51:
        return (FanP51, model, XiaomiFanP51)
    if model == MODEL_FAN_P28:
        return (FanP28, model, XiaomiFanP28)
    if model == MODEL_FAN_2LITE:
        return (Fan2Lite, model, XiaomiFan2Lite)

    return None


def build_fan_client(host: str, token: str, model: str):
    """Instantiate the right miio client for a model, or None if unsupported.

    Used once per config entry (in `__init__.py`), so the same client object
    can be shared between the fan entity and the read-only monitoring
    entities (sensor/binary_sensor) via one coordinator.
    """
    spec = _model_spec(model)
    if spec is None:
        return None
    client_cls, client_model, _entity_cls = spec
    return client_cls(host, token, model=client_model)


def _build_device(fan, model, name, unique_id, retries, preset_modes_override):
    """Instantiate the HA entity wrapping an already-built miio client."""
    spec = _model_spec(model)
    if spec is None:
        return None
    _client_cls, _client_model, entity_cls = spec
    return entity_cls(name, fan, model, unique_id, retries, preset_modes_override)


def get_available_attributes(model: str) -> dict[str, str]:
    """Return the status attributes a model exposes, keyed by ATTR_* name.

    Used by the sensor/binary_sensor platforms to know which monitoring
    entities to create for a model, without duplicating the per-model
    attribute tables each XiaomiFan* entity class already defines in its
    `__init__` (`self._available_attributes = AVAILABLE_ATTRIBUTES_FAN_*`).
    Building a throwaway entity instance is cheap and side-effect free -
    `__init__` on every one of these classes only assigns attributes, it
    never talks to the device - but is wrapped defensively in case a future
    model class breaks that assumption.
    """
    spec = _model_spec(model)
    if spec is None:
        return {}
    _client_cls, _client_model, entity_cls = spec
    try:
        probe = entity_cls("", None, model, None, DEFAULT_RETRIES, None)
    except Exception:
        _LOGGER.debug(
            "Could not determine available attributes for model %s",
            model,
            exc_info=True,
        )
        return {}
    return dict(getattr(probe, "_available_attributes", {}))


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add the fan entity that `__init__.py` already built for this entry.

    Connecting to the device, picking its model, and building the shared
    miio client *and* this entity all happen once, in `__init__.py`'s
    `async_setup_entry` - before any platform (this one, sensor,
    binary_sensor, switch) is forwarded - so that every platform shares the
    exact same client object, coordinator, and (for switches, which delegate
    their commands to it) fan entity, instead of each building its own.
    Constructing an entity object has no side effects on its own - nothing
    here talks to `hass` or the device until it's added below - so building
    it ahead of time in `__init__.py` is safe.
    """
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    device = entry.runtime_data.fan_entity

    hass.data[DATA_KEY][entry.entry_id] = device
    async_add_entities([device], update_before_add=True)

    if hass.data.get(DATA_SERVICES_REGISTERED):
        return
    hass.data[DATA_SERVICES_REGISTERED] = True

    async def async_service_handler(service):
        """Map services to methods on XiaomiFan."""
        method = SERVICE_TO_METHOD.get(service.service)
        params = {
            key: value for key, value in service.data.items() if key != ATTR_ENTITY_ID
        }
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            devices = [
                device
                for device in hass.data[DATA_KEY].values()
                if device.entity_id in entity_ids
            ]
        else:
            devices = hass.data[DATA_KEY].values()

        update_tasks = []
        for device in devices:
            if not hasattr(device, method["method"]):
                continue
            await getattr(device, method["method"])(**params)
            update_tasks.append(asyncio.create_task(device.async_update_ha_state(True)))

        if update_tasks:
            await asyncio.wait(update_tasks)

    for air_purifier_service, air_purifier_method in SERVICE_TO_METHOD.items():
        schema = air_purifier_method.get("schema", AIRPURIFIER_SERVICE_SCHEMA)
        hass.services.async_register(
            DOMAIN, air_purifier_service, async_service_handler, schema=schema
        )


class XiaomiGenericDevice(FanEntity):
    """Representation of a generic Xiaomi device."""

    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the generic Xiaomi device."""
        self._name = name
        self._device = device
        self._model = model
        self._unique_id = unique_id
        self._retry = 0
        self._retries = retries
        self._preset_modes_override = preset_modes_override

        self._available = False
        self._state = None
        self._state_attrs = {ATTR_MODEL: self._model}
        self._device_features = FEATURE_SET_BUZZER
        self._skip_update = False
        self.sw_version = None
        self._device_id: int | None = None
        self._last_heal_attempt: float | None = None

    @property
    def supported_features(self):
        """Flag supported features."""
        return 0

    @property
    def should_poll(self):
        """Poll the device."""
        return True

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info so the fan gets its own device page."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._unique_id or f"{self._model}-{self._name}")},
            name=self._name,
            manufacturer="Xiaomi",
            model=self._model,
            sw_version=self.sw_version,
        )

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def extra_state_attributes(self):
        """Return the extra state attributes of the device."""
        return self._state_attrs

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @staticmethod
    def _extract_value_from_attribute(state, attribute):
        value = getattr(state, attribute, None)
        if isinstance(value, Enum):
            return value.value

        return value

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a miio device command handling error messages."""
        try:
            result = await self.hass.async_add_executor_job(
                partial(func, *args, **kwargs)
            )

            _LOGGER.debug("Response received from miio device: %s", result)

            return result == SUCCESS
        except FanException as exc:
            _LOGGER.warning(mask_error, exc)
            return False
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            self._available = False
            return False

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        if percentage == 0 or preset_mode == SPEED_OFF:
            await self.async_turn_off(**kwargs)
            return

        if percentage is not None:
            await self.async_set_percentage(percentage)
        elif preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        else:
            result = await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )

            if not result:
                return

        self._state = True
        self._skip_update = True

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the device off."""
        result = await self._try_command(
            "Turning the miio device off failed.", self._device.off
        )

        if result:
            self._state = False
            self._skip_update = True

    async def _async_set_feature(
        self, feature: int, mask_error: str, func, *args
    ) -> bool:
        """Run a device command only if this model supports `feature`.

        Returns True when the command was issued and the device acknowledged it.
        """
        if self._device_features & feature == 0:
            return False

        return await self._try_command(mask_error, func, *args)

    async def async_set_buzzer_on(self):
        """Turn the buzzer on."""
        await self._async_set_feature(
            FEATURE_SET_BUZZER,
            "Turning the buzzer of the miio device on failed.",
            self._device.set_buzzer,
            True,
        )

    async def async_set_buzzer_off(self):
        """Turn the buzzer off."""
        await self._async_set_feature(
            FEATURE_SET_BUZZER,
            "Turning the buzzer of the miio device off failed.",
            self._device.set_buzzer,
            False,
        )

    async def async_set_child_lock_on(self):
        """Turn the child lock on."""
        await self._async_set_feature(
            FEATURE_SET_CHILD_LOCK,
            "Turning the child lock of the miio device on failed.",
            self._device.set_child_lock,
            True,
        )

    async def async_set_child_lock_off(self):
        """Turn the child lock off."""
        await self._async_set_feature(
            FEATURE_SET_CHILD_LOCK,
            "Turning the child lock of the miio device off failed.",
            self._device.set_child_lock,
            False,
        )

    async def _async_handle_update_failure(self, ex: DeviceException) -> None:
        """Count a failed poll; auto-heal the host if possible, else go unavailable."""
        self._retry += 1
        if self._retry < self._retries:
            _LOGGER.info(
                "%s Got exception while fetching the state: %s , _retry=%s",
                self.__class__.__name__,
                ex,
                self._retry,
            )
            return

        if await self._async_try_heal_host(ex):
            self._retry = 0
            return

        self._available = False
        _LOGGER.error(
            "%s Got exception while fetching the state: %s , _retry=%s",
            self.__class__.__name__,
            ex,
            self._retry,
        )

    def _set_device_host(self, new_host: str) -> bool:
        """Point the miio client at a new IP; False if python-miio changed shape.

        python-miio keeps the address both on the device and on its protocol
        object, with no public setter. Verify both exist before touching
        either, so an incompatible library version degrades to "no auto-heal"
        instead of an AttributeError or a half-updated client.
        """
        protocol = getattr(self._device, "_protocol", None)
        if protocol is None or not hasattr(protocol, "ip"):
            _LOGGER.warning(
                "%s: python-miio internals changed; cannot switch host in place",
                self._name,
            )
            return False

        self._device.ip = new_host
        protocol.ip = new_host
        return True

    async def _async_try_heal_host(self, ex: DeviceException) -> bool:
        """Best-effort: locate this device's new IP by its miIO device ID.

        IP addresses change (DHCP lease renewals, router reboots), but the
        device's own miIO device ID doesn't. When a fan goes consistently
        unreachable at its configured host, broadcast a discovery handshake
        on the LAN and, if this device answers from a different IP, switch
        to it in place and persist the new host to the config entry.
        """
        if self._device_id is None:
            return False

        # A fan that stays offline would otherwise trigger a LAN broadcast on
        # every poll once its retries are exhausted; rate-limit the scans.
        now = time.monotonic()
        if (
            self._last_heal_attempt is not None
            and now - self._last_heal_attempt < HEAL_COOLDOWN_SECONDS
        ):
            return False
        self._last_heal_attempt = now

        _LOGGER.warning(
            "%s unreachable at %s after %s attempts (%s); scanning the "
            "network for its new IP",
            self._name,
            self._device.ip,
            self._retries,
            ex,
        )
        found = await self.hass.async_add_executor_job(broadcast_discover_device_ids)
        new_host = found.get(self._device_id)
        if not new_host or new_host == self._device.ip:
            return False

        _LOGGER.info(
            "Found %s at %s (was %s); switching to the new address",
            self._name,
            new_host,
            self._device.ip,
        )
        if not self._set_device_host(new_host):
            return False

        if self.registry_entry is not None and self.registry_entry.config_entry_id:
            entry = self.hass.config_entries.async_get_entry(
                self.registry_entry.config_entry_id
            )
            if entry is not None:
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_HOST: new_host}
                )

        return True


class XiaomiFan(XiaomiGenericDevice):
    """Representation of a Xiaomi Pedestal Fan."""

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the fan entity."""
        super().__init__(name, device, model, unique_id, retries, preset_modes_override)

        self._device_features = FEATURE_FLAGS_FAN
        self._available_attributes = AVAILABLE_ATTRIBUTES_FAN
        self._percentage = None
        self._preset_modes = list(FAN_PRESET_MODES)
        if preset_modes_override is not None:
            self._preset_modes = preset_modes_override

        self._preset_mode = None
        self._oscillate = None
        self._natural_mode = False

        self._state_attrs.update(
            {attribute: None for attribute in self._available_attributes}
        )

    @property
    def supported_features(self) -> int:
        """Supported features."""
        return (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.OSCILLATE
            | FanEntityFeature.DIRECTION
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

    async def async_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._oscillate = state.oscillate
            self._natural_mode = state.natural_speed != 0
            self._state = state.is_on

            if self._natural_mode:
                for preset_mode, range in FAN_PRESET_MODES.items():
                    if state.natural_speed in range:
                        self._preset_mode = preset_mode
                        self._percentage = state.natural_speed
                        break
            else:
                for preset_mode, range in FAN_PRESET_MODES.items():
                    if state.direct_speed in range:
                        self._preset_mode = preset_mode
                        self._percentage = state.direct_speed
                        break

            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                }
            )
            self._retry = 0

        except DeviceException as ex:
            await self._async_handle_update_failure(ex)

    @property
    def percentage(self):
        """Return the current speed."""
        return self._percentage

    @property
    def preset_modes(self):
        """Get the list of available preset modes."""
        return self._preset_modes

    @property
    def preset_mode(self):
        """Get the current preset mode."""
        return self._preset_mode

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug("Setting the preset mode to: %s", preset_mode)

        if preset_mode == SPEED_OFF:
            await self.async_turn_off()
            return

        if self._natural_mode:
            await self._try_command(
                "Setting fan speed of the miio device failed.",
                self._device.set_natural_speed,
                FAN_PRESET_MODE_VALUES[preset_mode],
            )
        else:
            await self._try_command(
                "Setting fan speed of the miio device failed.",
                self._device.set_direct_speed,
                FAN_PRESET_MODE_VALUES[preset_mode],
            )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        _LOGGER.debug("Setting the fan speed percentage to: %s", percentage)

        if percentage == 0:
            await self.async_turn_off()
            return

        if self._natural_mode:
            await self._try_command(
                "Setting fan speed percentage of the miio device failed.",
                self._device.set_natural_speed,
                percentage,
            )
        else:
            await self._try_command(
                "Setting fan speed percentage of the miio device failed.",
                self._device.set_direct_speed,
                percentage,
            )

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        if direction == "forward":
            direction = "right"

        if direction == "reverse":
            direction = "left"

        if self._oscillate:
            await self._try_command(
                "Setting oscillate off of the miio device failed.",
                self._device.set_oscillate,
                False,
            )

        await self._try_command(
            "Setting move direction of the miio device failed.",
            self._device.set_rotate,
            FanMoveDirection(direction),
        )

    @property
    def oscillating(self):
        """Return the oscillation state."""
        return self._oscillate

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        if oscillating:
            await self._try_command(
                "Setting oscillate on of the miio device failed.",
                self._device.set_oscillate,
                True,
            )
        else:
            await self._try_command(
                "Setting oscillate off of the miio device failed.",
                self._device.set_oscillate,
                False,
            )

    async def async_set_oscillation_angle(self, angle: int) -> None:
        """Set oscillation angle."""
        if self._device_features & FEATURE_SET_OSCILLATION_ANGLE == 0:
            return

        await self._try_command(
            "Setting angle of the miio device failed.", self._device.set_angle, angle
        )

    async def async_set_delay_off(self, delay_off_countdown: int) -> None:
        """Set scheduled off timer in minutes."""

        await self._try_command(
            "Setting delay off miio device failed.",
            self._device.delay_off,
            delay_off_countdown * 60,
        )

    async def async_set_led_brightness(self, brightness: int = 2):
        """Set the led brightness."""
        if self._device_features & FEATURE_SET_LED_BRIGHTNESS == 0:
            return

        await self._try_command(
            "Setting the led brightness of the miio device failed.",
            self._device.set_led_brightness,
            FanLedBrightness(brightness),
        )

    async def async_set_natural_mode_on(self):
        """Turn the natural mode on."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return

        self._natural_mode = True
        await self.async_set_percentage(self._percentage)

    async def async_set_natural_mode_off(self):
        """Turn the natural mode off."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return

        self._natural_mode = False
        await self.async_set_percentage(self._percentage)

    async def async_set_vertical_oscillation_angle(self, vertical_angle: int) -> None:
        """Set vertical oscillation angle."""
        if self._device_features & FEATURE_SET_VERTICAL_OSCILLATION_ANGLE == 0:
            return

        await self._try_command(
            "Setting vertical oscillation angle of the miio device failed.",
            self._device.set_vertical_angle,
            vertical_angle,
        )


class XiaomiFanP5(XiaomiFan):
    """Representation of a Xiaomi Pedestal Fan P5."""

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the fan entity."""
        super().__init__(name, device, model, unique_id, retries, preset_modes_override)

        self._device_features = FEATURE_FLAGS_FAN_P5
        self._available_attributes = AVAILABLE_ATTRIBUTES_FAN_P5
        self._percentage = None
        self._preset_modes = list(FAN_PRESET_MODES)
        if preset_modes_override is not None:
            self._preset_modes = preset_modes_override

        self._preset_mode = None
        self._oscillate = None
        self._natural_mode = False

        self._state_attrs.update(
            {attribute: None for attribute in self._available_attributes}
        )

    async def async_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._percentage = state.speed
            self._oscillate = state.oscillate
            self._natural_mode = state.mode == FanOperationMode.Nature
            self._state = state.is_on

            for preset_mode, range in FAN_PRESET_MODES.items():
                if state.speed in range:
                    self._preset_mode = preset_mode
                    break

            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                }
            )

            self._retry = 0

        except DeviceException as ex:
            await self._async_handle_update_failure(ex)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug("Setting the preset mode to: %s", preset_mode)

        if preset_mode == SPEED_OFF:
            await self.async_turn_off()
            return

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )
        await self._try_command(
            "Setting fan speed of the miio device failed.",
            self._device.set_speed,
            FAN_PRESET_MODE_VALUES_P5[preset_mode],
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        _LOGGER.debug("Setting the fan speed percentage to: %s", percentage)

        if percentage == 0:
            await self.async_turn_off()
            return

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )
        await self._try_command(
            "Setting fan speed percentage of the miio device failed.",
            self._device.set_speed,
            percentage,
        )

    async def async_set_natural_mode_on(self):
        """Turn the natural mode on."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return

        await self._try_command(
            "Turning on natural mode of the miio device failed.",
            self._device.set_mode,
            FanOperationMode.Nature,
        )

    async def async_set_natural_mode_off(self):
        """Turn the natural mode off."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return

        await self._try_command(
            "Turning on natural mode of the miio device failed.",
            self._device.set_mode,
            FanOperationMode.Normal,
        )

    async def async_set_delay_off(self, delay_off_countdown: int) -> None:
        """Set scheduled off timer in minutes."""

        await self._try_command(
            "Setting delay off miio device failed.",
            self._device.delay_off,
            delay_off_countdown,
        )

    async def async_set_led_brightness(self, brightness: int = 2):
        """Set LED on (brightness != 2) or off (brightness == 2)."""
        if self._device_features & FEATURE_SET_LED == 0:
            return
        await self._try_command(
            "Setting LED of the miio device failed.",
            self._device.set_led,
            brightness != 2,
        )


class XiaomiFanMiot(XiaomiFanP5):
    """Representation of a Xiaomi Pedestal Fan P9, P10, P11, P18, P30."""

    pass


class XiaomiFanLeshow(XiaomiGenericDevice):
    """Representation of a Xiaomi Fan Leshow SS4."""

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the fan entity."""
        super().__init__(name, device, model, unique_id, retries, preset_modes_override)

        self._device_features = FEATURE_FLAGS_FAN_LESHOW_SS4
        self._available_attributes = AVAILABLE_ATTRIBUTES_FAN_LESHOW_SS4
        self._percentage = None
        self._preset_modes = [mode.name for mode in FanLeshowOperationMode]
        if preset_modes_override is not None:
            self._preset_modes = preset_modes_override
        self._oscillate = None

        self._state_attrs.update(
            {attribute: None for attribute in self._available_attributes}
        )

    @property
    def supported_features(self) -> int:
        """Supported features."""
        return (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.OSCILLATE
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

    async def async_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._percentage = state.speed
            self._oscillate = state.oscillate
            self._state = state.is_on

            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                }
            )
            self._retry = 0

        except DeviceException as ex:
            await self._async_handle_update_failure(ex)

    @property
    def percentage(self):
        """Return the current speed."""
        return self._percentage

    @property
    def preset_modes(self):
        """Get the list of available preset modes."""
        return self._preset_modes

    @property
    def preset_mode(self):
        """Get the current preset mode."""
        if self._state:
            return FanLeshowOperationMode(self._state_attrs[ATTR_MODE]).name

        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug("Setting the preset mode to: %s", preset_mode)

        await self._try_command(
            "Setting preset mode of the miio device failed.",
            self._device.set_mode,
            FanLeshowOperationMode[preset_mode.title()],
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        _LOGGER.debug("Setting the fan speed percentage to: %s", percentage)

        if percentage == 0:
            await self.async_turn_off()
            return

        await self._try_command(
            "Setting fan speed percentage of the miio device failed.",
            self._device.set_speed,
            percentage,
        )

    @property
    def oscillating(self):
        """Return the oscillation state."""
        return self._oscillate

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        if oscillating:
            await self._try_command(
                "Setting oscillate on of the miio device failed.",
                self._device.set_oscillate,
                True,
            )
        else:
            await self._try_command(
                "Setting oscillate off of the miio device failed.",
                self._device.set_oscillate,
                False,
            )

    async def async_set_delay_off(self, delay_off_countdown: int) -> None:
        """Set scheduled off timer in minutes."""

        await self._try_command(
            "Setting delay off miio device failed.",
            self._device.delay_off,
            delay_off_countdown,
        )


class XiaomiFan1C(XiaomiFan):
    """Representation of a Xiaomi Fan 1C."""

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the fan entity."""
        super().__init__(name, device, model, unique_id, retries, preset_modes_override)

        self._device_features = FEATURE_FLAGS_FAN_1C
        self._available_attributes = AVAILABLE_ATTRIBUTES_FAN_1C
        self._preset_modes = list(FAN_PRESET_MODES_1C)
        if preset_modes_override is not None:
            self._preset_modes = preset_modes_override

        self._oscillate = None

        self._state_attrs.update(
            {attribute: None for attribute in self._available_attributes}
        )

    @property
    def supported_features(self) -> int:
        """Supported features."""
        return (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.OSCILLATE
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

    async def async_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._oscillate = state.oscillate
            self._state = state.is_on

            for preset_mode, value in FAN_PRESET_MODES_1C.items():
                if state.speed == value:
                    self._preset_mode = preset_mode

            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                }
            )
            self._retry = 0

        except DeviceException as ex:
            await self._async_handle_update_failure(ex)

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self._preset_mode not in FAN_SPEEDS_1C:
            return None
        return ordered_list_item_to_percentage(FAN_SPEEDS_1C, self._preset_mode)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(FAN_SPEEDS_1C)

    @property
    def preset_modes(self):
        """Get the list of available preset modes."""
        return self._preset_modes

    @property
    def preset_mode(self):
        """Get the current preset mode."""
        if self._state:
            return self._preset_mode

        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug("Setting the preset mode to: %s", preset_mode)

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )
        await self._try_command(
            "Setting preset mode of the miio device failed.",
            self._device.set_speed,
            FAN_PRESET_MODES_1C[preset_mode],
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        _LOGGER.debug("Setting the fan speed percentage to: %s", percentage)

        if percentage == 0:
            await self.async_turn_off()
            return

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )
        await self._try_command(
            "Setting preset mode of the miio device failed.",
            self._device.set_speed,
            FAN_PRESET_MODES_1C[
                percentage_to_ordered_list_item(FAN_SPEEDS_1C, percentage)
            ],
        )

    @property
    def oscillating(self):
        """Return the oscillation state."""
        return self._oscillate

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        if oscillating:
            await self._try_command(
                "Setting oscillate on of the miio device failed.",
                self._device.set_oscillate,
                True,
            )
        else:
            await self._try_command(
                "Setting oscillate off of the miio device failed.",
                self._device.set_oscillate,
                False,
            )

    async def async_set_delay_off(self, delay_off_countdown: int) -> None:
        """Set scheduled off timer in minutes."""

        await self._try_command(
            "Setting delay off miio device failed.",
            self._device.delay_off,
            delay_off_countdown,
        )

    async def async_set_led_brightness(self, brightness: int = 2):
        """Set LED on (brightness != 2) or off (brightness == 2)."""
        if self._device_features & FEATURE_SET_LED == 0:
            return
        await self._try_command(
            "Setting LED of the miio device failed.",
            self._device.set_led,
            brightness != 2,
        )

    async def async_set_natural_mode_on(self):
        """Turn the natural mode on."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return

        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            FanOperationMode.Nature,
        )

    async def async_set_natural_mode_off(self):
        """Turn the natural mode off."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return

        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            FanOperationMode.Normal,
        )


class XiaomiFanZA5(XiaomiFan):
    """Representation of a Xiaomi Fan ZA5."""

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the fan entity."""
        super().__init__(name, device, model, unique_id, retries, preset_modes_override)

        self._device_features = FEATURE_FLAGS_FAN_ZA5
        self._available_attributes = AVAILABLE_ATTRIBUTES_FAN_ZA5
        self._preset_modes = list(FAN_PRESET_MODES_ZA5)
        if preset_modes_override is not None:
            self._preset_modes = preset_modes_override

        self._state_attrs.update(
            {attribute: None for attribute in self._available_attributes}
        )

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return (
            FanEntityFeature.DIRECTION
            | FanEntityFeature.OSCILLATE
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

    async def async_update(self):
        """Fetch state from the device."""
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._percentage = state.fan_speed
            self._oscillate = state.swing_mode
            self._natural_mode = state.mode == FanOperationMode.Nature
            self._state = state.power

            for preset_mode, speed_range in FAN_PRESET_MODES.items():
                if state.fan_speed in speed_range:
                    self._preset_mode = preset_mode
                    break

            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                    if hasattr(state, value)
                }
            )
            self._retry = 0
        except DeviceException as ex:
            await self._async_handle_update_failure(ex)

    @property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage."""
        return self._percentage

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return 100

    @property
    def preset_modes(self):
        """Return the list of available preset modes."""
        return self._preset_modes

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        if self._state:
            return self._preset_mode
        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug("Setting the preset mode to: %s", preset_mode)

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )
        await self._try_command(
            "Setting preset mode of the miio device failed.",
            self._device.set_speed,
            FAN_PRESET_MODES_ZA5[preset_mode],
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        _LOGGER.debug("Setting the fan speed percentage to: %s", percentage)

        if percentage == 0:
            await self.async_turn_off()
            return

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )
        await self._try_command(
            "Setting preset mode of the miio device failed.",
            self._device.set_speed,
            percentage,
        )

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        if oscillating:
            await self._try_command(
                "Setting oscillate on of the miio device failed.",
                self._device.set_oscillate,
                True,
            )
        else:
            await self._try_command(
                "Setting oscillate off of the miio device failed.",
                self._device.set_oscillate,
                False,
            )

    async def async_set_delay_off(self, delay_off_countdown: int) -> None:
        """Set scheduled off timer in minutes."""

        await self._try_command(
            "Setting delay off miio device failed.",
            self._device.delay_off,
            delay_off_countdown * 60,
        )

    async def async_set_natural_mode_on(self):
        """Turn the natural mode on."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return

        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            FanOperationMode.Nature,
        )

    async def async_set_natural_mode_off(self):
        """Turn the natural mode off."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return

        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            FanOperationMode.Normal,
        )

    async def async_set_led_brightness(self, brightness: int = 2):
        """Set the led brightness."""
        brightness = FanLedBrightness(brightness)
        if brightness == FanLedBrightness.Bright:
            brightness = 100
        elif brightness == FanLedBrightness.Dim:
            brightness = 1
        else:
            brightness = 0
        await self.async_set_raw_led_brightness(brightness)

    async def async_set_raw_led_brightness(self, brightness: int):
        """Set the raw led brightness."""
        if self._device_features & FEATURE_SET_LED_BRIGHTNESS == 0:
            return

        await self._try_command(
            "Setting the led brightness of the miio device failed.",
            self._device.set_light,
            brightness,
        )

    async def async_set_anion_on(self):
        """Turn anion on."""
        if self._device_features & FEATURE_SET_ANION == 0:
            return

        await self._try_command(
            "Setting anion of the miio device failed.",
            self._device.set_anion,
            True,
        )

    async def async_set_anion_off(self):
        """Turn anion off."""
        if self._device_features & FEATURE_SET_ANION == 0:
            return

        await self._try_command(
            "Setting anion of the miio device failed.",
            self._device.set_anion,
            False,
        )


class XiaomiFanP33(XiaomiFanMiot):
    """Representation of a Xiaomi Fan P33."""

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the fan entity."""
        super().__init__(name, device, model, unique_id, retries, preset_modes_override)

        self._device_features = FEATURE_FLAGS_FAN_P33
        self._available_attributes = AVAILABLE_ATTRIBUTES_FAN_P33
        self._percentage = None
        self._preset_modes = list(FAN_PRESET_MODES_P33)
        if preset_modes_override is not None:
            self._preset_modes = preset_modes_override

        self._preset_mode = None
        self._oscillate = None
        self._natural_mode = False

        self._state_attrs.update(
            {attribute: None for attribute in self._available_attributes}
        )

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return (
            FanEntityFeature.DIRECTION
            | FanEntityFeature.OSCILLATE
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

    """
    TODO:
    - setting child lock works, but HA always reads the value as null
    """

    async def async_update(self):
        """Fetch state from the device."""
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._percentage = state.percentage
            self._oscillate = state.oscillate
            self._natural_mode = state.mode == OperationModeFanP33.Nature
            self._state = state.power

            for preset_mode, speed_range in FAN_PRESET_MODES.items():
                if state.percentage in speed_range:
                    self._preset_mode = preset_mode
                    break

            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                    if hasattr(state, value)
                }
            )
            self._retry = 0

        except DeviceException as ex:
            await self._async_handle_update_failure(ex)

    @property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage."""
        return self._percentage

    @property
    def preset_modes(self):
        """Return the list of available preset modes."""
        return self._preset_modes

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        if self._state:
            return self._preset_mode
        return None

    async def async_set_natural_mode_on(self):
        """Turn the natural mode on."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return

        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP33.Nature,
        )

    async def async_set_natural_mode_off(self):
        """Turn the natural mode off."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return

        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP33.Normal,
        )


class XiaomiFanP39(XiaomiFanMiot):
    """Representation of a Xiaomi Fan P39."""

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the fan entity."""
        super().__init__(name, device, model, unique_id, retries, preset_modes_override)

        self._device_features = FEATURE_FLAGS_FAN_P39
        self._available_attributes = AVAILABLE_ATTRIBUTES_FAN_P39
        self._percentage = None
        self._preset_modes = list(FAN_PRESET_MODES_P39)
        if preset_modes_override is not None:
            self._preset_modes = preset_modes_override

        self._preset_mode = None
        self._oscillate = None
        self._natural_mode = False

        self._state_attrs.update(
            {attribute: None for attribute in self._available_attributes}
        )

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return (
            FanEntityFeature.DIRECTION
            | FanEntityFeature.OSCILLATE
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

    async def async_update(self):
        """Fetch state from the device."""
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._percentage = state.fan_speed
            self._oscillate = state.oscillate
            self._natural_mode = state.mode == OperationModeFanP39.Nature
            self._state = state.power

            for preset_mode, speed_range in FAN_PRESET_MODES.items():
                if state.fan_speed in speed_range:
                    self._preset_mode = preset_mode
                    break

            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                    if hasattr(state, value)
                }
            )
            self._retry = 0

        except DeviceException as ex:
            await self._async_handle_update_failure(ex)

    @property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage."""
        return self._percentage

    @property
    def preset_modes(self):
        """Return the list of available preset modes."""
        return self._preset_modes

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        if self._state:
            return self._preset_mode
        return None

    async def async_set_natural_mode_on(self):
        """Turn the natural mode on."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return

        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP39.Nature,
        )

    async def async_set_natural_mode_off(self):
        """Turn the natural mode off."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return

        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP39.Normal,
        )


class XiaomiFanP45(XiaomiFanMiot):
    """Representation of the Xiaomi Smart Tower Fan 2 (xiaomi.fan.p45)."""

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the fan entity."""
        super().__init__(name, device, model, unique_id, retries, preset_modes_override)

        self._device_features = FEATURE_FLAGS_FAN_P45
        self._available_attributes = AVAILABLE_ATTRIBUTES_FAN_P45
        self._percentage = None
        self._preset_modes = list(FAN_PRESET_MODES_P45)
        if preset_modes_override is not None:
            self._preset_modes = preset_modes_override

        self._preset_mode = None
        self._oscillate = None
        self._natural_mode = False

        self._state_attrs = {
            ATTR_MODEL: self._model,
            **{attribute: None for attribute in self._available_attributes},
        }

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return (
            FanEntityFeature.OSCILLATE
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

    async def async_update(self):
        """Fetch state from the device."""
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._percentage = state.fan_speed
            self._oscillate = state.horizontal_swing
            self._natural_mode = state.mode == OperationModeFanP45.Natural.name
            self._state = state.power

            if state.mode == OperationModeFanP45.Sleep.name:
                self._preset_mode = FAN_PRESET_MODE_SLEEP
            else:
                self._preset_mode = None
                for preset_mode, value in FAN_PRESET_MODES_P45.items():
                    if preset_mode in (SPEED_OFF, FAN_PRESET_MODE_SLEEP):
                        continue
                    is_natural = preset_mode.startswith("Natural")
                    if state.fan_level == value and is_natural == self._natural_mode:
                        self._preset_mode = preset_mode
                        break

            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                    if hasattr(state, value)
                }
            )
            self._retry = 0

        except DeviceException as ex:
            await self._async_handle_update_failure(ex)

    @property
    def percentage(self):
        """Return the current percentage."""
        return self._percentage

    @property
    def preset_modes(self):
        """Return the list of available preset modes."""
        return self._preset_modes

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        if self._state:
            return self._preset_mode
        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode.

        Combines level (1..4) with Straight/Natural mode, or selects standalone Sleep mode.
        """
        _LOGGER.debug("Setting the preset mode to: %s", preset_mode)

        if preset_mode == SPEED_OFF:
            await self.async_turn_off()
            return

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )

        if preset_mode == FAN_PRESET_MODE_SLEEP:
            await self._try_command(
                "Setting fan mode failed.",
                self._device.set_mode,
                OperationModeFanP45.Sleep,
            )
            return

        natural = preset_mode.startswith("Natural")
        await self._try_command(
            "Setting fan mode failed.",
            self._device.set_mode,
            OperationModeFanP45.Natural if natural else OperationModeFanP45.Straight,
        )
        await self._try_command(
            "Setting fan level of the miio device failed.",
            self._device.set_fan_level,
            FAN_PRESET_MODES_P45[preset_mode],
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        _LOGGER.debug("Setting the fan speed percentage to: %s", percentage)

        if percentage == 0:
            await self.async_turn_off()
            return

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )

        await self._try_command(
            "Setting fan speed percentage of the miio device failed.",
            self._device.set_speed,
            percentage,
        )

    async def async_set_natural_mode_on(self):
        """Turn the natural mode on."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP45.Natural,
        )

    async def async_set_natural_mode_off(self):
        """Turn the natural mode off."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP45.Straight,
        )

    async def async_turn(self, direction: str):
        """Turn fan in the given direction."""
        if self._device_features & FEATURE_TURN == 0:
            return
        await self._try_command(
            "Turning the miio device failed.",
            self._device.turn,
            direction,
        )


class XiaomiFanP76(XiaomiFanP33):
    """Representation of a Xiaomi Fan P76."""

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the fan entity."""
        super().__init__(name, device, model, unique_id, retries, preset_modes_override)

        self._device_features = FEATURE_FLAGS_FAN_P76
        self._available_attributes = AVAILABLE_ATTRIBUTES_FAN_P76
        self._percentage = None
        self._preset_modes = list(FAN_PRESET_MODES_P76)
        if preset_modes_override is not None:
            self._preset_modes = preset_modes_override

        self._preset_mode = None
        self._oscillate = None
        self._vertical_oscillate = None
        self._natural_mode = False

        self._state_attrs = {
            ATTR_MODEL: self._model,
            **{attribute: None for attribute in self._available_attributes},
        }

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return (
            FanEntityFeature.OSCILLATE
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.DIRECTION
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

    @property
    def current_direction(self) -> str | None:
        """Return the current direction."""
        if self._vertical_oscillate is None:
            return None
        return "forward" if self._vertical_oscillate else "reverse"

    async def async_set_direction(self, direction: str) -> None:
        """Set the fan direction."""
        if direction == "forward":
            await self.async_set_vertical_oscillation_on()
            self._vertical_oscillate = True
        else:
            await self.async_set_vertical_oscillation_off()
            self._vertical_oscillate = False
        self.async_write_ha_state()

    async def async_update(self):
        """Fetch state from the device."""
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._percentage = state.fan_speed
            self._oscillate = state.horizontal_swing
            self._vertical_oscillate = state.vertical_swing
            self._natural_mode = state.mode == OperationModeFanP76.Natural.name
            self._state = state.power

            for preset_mode, value in FAN_PRESET_MODES_P76.items():
                if preset_mode == SPEED_OFF:
                    continue
                is_natural = preset_mode.startswith("Natural")
                if state.fan_level == value and is_natural == self._natural_mode:
                    self._preset_mode = preset_mode
                    break

            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                    if hasattr(state, value)
                }
            )
            self._retry = 0

        except DeviceException as ex:
            await self._async_handle_update_failure(ex)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug("Setting the preset mode to: %s", preset_mode)

        if preset_mode == SPEED_OFF:
            await self.async_turn_off()
            return

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )

        natural = preset_mode.startswith("Natural")
        await self._try_command(
            "Setting fan mode failed.",
            self._device.set_mode,
            OperationModeFanP76.Natural if natural else OperationModeFanP76.Straight,
        )
        await self._try_command(
            "Setting fan level of the miio device failed.",
            self._device.set_fan_level,
            FAN_PRESET_MODES_P76[preset_mode],
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        _LOGGER.debug("Setting the fan speed percentage to: %s", percentage)

        if percentage == 0:
            await self.async_turn_off()
            return

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )
        await self._try_command(
            "Setting fan speed percentage of the miio device failed.",
            self._device.set_speed,
            percentage,
        )

    async def async_set_natural_mode_on(self):
        """Turn the natural mode on."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP76.Natural,
        )

    async def async_set_natural_mode_off(self):
        """Turn the natural mode off."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP76.Straight,
        )

    async def async_set_led_brightness(self, brightness: int = 2):
        """Set LED on (brightness != 2) or off (brightness == 2)."""
        if self._device_features & FEATURE_SET_LED == 0:
            return
        await self._try_command(
            "Setting LED of the miio device failed.",
            self._device.set_light,
            brightness != 2,
        )

    async def async_set_vertical_oscillation_on(self):
        """Turn vertical oscillation on."""
        if self._device_features & FEATURE_SET_VERTICAL_OSCILLATION == 0:
            return
        await self._try_command(
            "Setting vertical oscillation on of the miio device failed.",
            self._device.set_vertical_oscillate,
            True,
        )

    async def async_set_vertical_oscillation_off(self):
        """Turn vertical oscillation off."""
        if self._device_features & FEATURE_SET_VERTICAL_OSCILLATION == 0:
            return
        await self._try_command(
            "Setting vertical oscillation off of the miio device failed.",
            self._device.set_vertical_oscillate,
            False,
        )

    async def async_turn(self, direction: str):
        """Turn fan in the given direction."""
        if self._device_features & FEATURE_TURN == 0:
            return
        await self._try_command(
            "Turning the miio device failed.",
            self._device.turn,
            direction,
        )


class XiaomiFanXiaomiP30(XiaomiFanP33):
    """Representation of the Xiaomi Fan P30 (xiaomi.fan.p30)."""

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the fan entity."""
        super().__init__(name, device, model, unique_id, retries, preset_modes_override)

        self._device_features = FEATURE_FLAGS_FAN_XIAOMI_P30
        self._available_attributes = AVAILABLE_ATTRIBUTES_FAN_XIAOMI_P30
        self._percentage = None
        self._preset_modes = list(FAN_PRESET_MODES_XIAOMI_P30)
        if preset_modes_override is not None:
            self._preset_modes = preset_modes_override

        self._preset_mode = None
        self._oscillate = None
        self._natural_mode = False

        self._state_attrs.update(
            {attribute: None for attribute in self._available_attributes}
        )

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return (
            FanEntityFeature.OSCILLATE
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

    async def async_update(self):
        """Fetch state from the device."""
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._percentage = state.fan_speed
            self._oscillate = state.horizontal_swing
            self._natural_mode = state.mode == OperationModeFanXiaomiP30.Nature.name
            self._state = state.power

            for preset_mode, value in FAN_PRESET_MODES_XIAOMI_P30.items():
                if preset_mode == SPEED_OFF:
                    continue
                is_natural = preset_mode.startswith("Natural")
                if state.fan_level == value and is_natural == self._natural_mode:
                    self._preset_mode = preset_mode
                    break

            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                    if hasattr(state, value)
                }
            )
            self._retry = 0

        except DeviceException as ex:
            await self._async_handle_update_failure(ex)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug("Setting the preset mode to: %s", preset_mode)

        if preset_mode == SPEED_OFF:
            await self.async_turn_off()
            return

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )

        natural = preset_mode.startswith("Natural")
        await self._try_command(
            "Setting fan mode failed.",
            self._device.set_mode,
            OperationModeFanXiaomiP30.Nature
            if natural
            else OperationModeFanXiaomiP30.Normal,
        )
        await self._try_command(
            "Setting fan level of the miio device failed.",
            self._device.set_fan_level,
            FAN_PRESET_MODES_XIAOMI_P30[preset_mode],
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        _LOGGER.debug("Setting the fan speed percentage to: %s", percentage)

        if percentage == 0:
            await self.async_turn_off()
            return

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )
        await self._try_command(
            "Setting fan speed percentage of the miio device failed.",
            self._device.set_speed,
            percentage,
        )

    async def async_set_natural_mode_on(self):
        """Turn the natural mode on."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanXiaomiP30.Nature,
        )

    async def async_set_natural_mode_off(self):
        """Turn the natural mode off."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanXiaomiP30.Normal,
        )

    async def async_set_led_brightness(self, brightness: int = 2):
        """Set LED on (brightness != 2) or off (brightness == 2)."""
        if self._device_features & FEATURE_SET_LED == 0:
            return
        await self._try_command(
            "Setting LED of the miio device failed.",
            self._device.set_light,
            brightness != 2,
        )

    async def async_turn(self, direction: str):
        """Turn fan in the given direction."""
        if self._device_features & FEATURE_TURN == 0:
            return
        await self._try_command(
            "Turning the miio device failed.",
            self._device.turn,
            direction,
        )


class XiaomiFanP70(XiaomiFanP33):
    """Representation of a Xiaomi Smart Desktop Air Circulation Fan P70."""

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the fan entity."""
        super().__init__(name, device, model, unique_id, retries, preset_modes_override)

        self._device_features = FEATURE_FLAGS_FAN_P70
        self._available_attributes = AVAILABLE_ATTRIBUTES_FAN_P70
        self._percentage = None
        self._preset_modes = list(FAN_PRESET_MODES_P70)
        if preset_modes_override is not None:
            self._preset_modes = preset_modes_override

        self._preset_mode = None
        self._oscillate = None
        self._vertical_oscillate = None
        self._natural_mode = False

        self._state_attrs = {
            ATTR_MODEL: self._model,
            **{attribute: None for attribute in self._available_attributes},
        }

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return (
            FanEntityFeature.OSCILLATE
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.DIRECTION
        )

    @property
    def current_direction(self) -> str | None:
        """Return the current direction."""
        if self._vertical_oscillate is None:
            return None
        return "forward" if self._vertical_oscillate else "reverse"

    async def async_set_direction(self, direction: str) -> None:
        """Set the fan direction."""
        if direction == "forward":
            await self.async_set_vertical_oscillation_on()
            self._vertical_oscillate = True
        else:
            await self.async_set_vertical_oscillation_off()
            self._vertical_oscillate = False
        self.async_write_ha_state()

    async def async_update(self):
        """Fetch state from the device."""
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._percentage = state.fan_speed
            self._oscillate = state.horizontal_swing
            self._vertical_oscillate = state.vertical_swing
            self._natural_mode = state.mode == OperationModeFanP70.Natural.name
            self._state = state.power

            for preset_mode, value in FAN_PRESET_MODES_P70.items():
                if state.fan_level == value:
                    self._preset_mode = preset_mode
                    break

            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                    if hasattr(state, value)
                }
            )
            self._retry = 0

        except DeviceException as ex:
            await self._async_handle_update_failure(ex)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug("Setting the preset mode to: %s", preset_mode)

        if preset_mode == SPEED_OFF:
            await self.async_turn_off()
            return

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )
        await self._try_command(
            "Setting fan level of the miio device failed.",
            self._device.set_fan_level,
            FAN_PRESET_MODES_P70[preset_mode],
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        _LOGGER.debug("Setting the fan speed percentage to: %s", percentage)

        if percentage == 0:
            await self.async_turn_off()
            return

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )
        await self._try_command(
            "Setting fan speed percentage of the miio device failed.",
            self._device.set_speed,
            percentage,
        )

    async def async_set_natural_mode_on(self):
        """Turn the natural mode on."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP70.Natural,
        )

    async def async_set_natural_mode_off(self):
        """Turn the natural mode off."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP70.Straight,
        )

    async def async_set_led_brightness(self, brightness: int = 2):
        """Set LED on (brightness != 2) or off (brightness == 2)."""
        if self._device_features & FEATURE_SET_LED == 0:
            return
        await self._try_command(
            "Setting LED of the miio device failed.",
            self._device.set_light,
            brightness != 2,
        )

    async def async_set_vertical_oscillation_on(self):
        """Turn vertical oscillation on."""
        if self._device_features & FEATURE_SET_VERTICAL_OSCILLATION == 0:
            return
        await self._try_command(
            "Setting vertical oscillation on of the miio device failed.",
            self._device.set_vertical_oscillate,
            True,
        )

    async def async_set_vertical_oscillation_off(self):
        """Turn vertical oscillation off."""
        if self._device_features & FEATURE_SET_VERTICAL_OSCILLATION == 0:
            return
        await self._try_command(
            "Setting vertical oscillation off of the miio device failed.",
            self._device.set_vertical_oscillate,
            False,
        )

    async def async_turn(self, direction: str):
        """Turn fan in the given direction."""
        if self._device_features & FEATURE_TURN == 0:
            return
        await self._try_command(
            "Turning the miio device failed.",
            self._device.turn,
            direction,
        )


class XiaomiFan2Lite(XiaomiFanP33):
    """Representation of a Mi Smart Standing Fan 2 Lite (xiaomi.fan.2lite)."""

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the fan entity."""
        super().__init__(name, device, model, unique_id, retries, preset_modes_override)

        self._device_features = FEATURE_FLAGS_FAN_2LITE
        self._available_attributes = AVAILABLE_ATTRIBUTES_FAN_2LITE
        self._percentage = None
        self._preset_modes = list(FAN_PRESET_MODES_2LITE)
        if preset_modes_override is not None:
            self._preset_modes = preset_modes_override

        self._preset_mode = None
        self._oscillate = None
        self._natural_mode = False

        self._state_attrs = {
            ATTR_MODEL: self._model,
            **{attribute: None for attribute in self._available_attributes},
        }

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return (
            FanEntityFeature.OSCILLATE
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return FAN_2LITE_SPEED_COUNT

    async def async_update(self):
        """Fetch state from the device."""
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._oscillate = state.horizontal_swing
            self._natural_mode = state.mode == OperationModeFan2Lite.Natural.name
            self._state = state.power
            self._preset_mode = FAN_PRESET_MODE_SLEEP if self._natural_mode else None

            if state.fan_level is None:
                self._percentage = None
            else:
                self._percentage = ranged_value_to_percentage(
                    (1, FAN_2LITE_SPEED_COUNT), state.fan_level + 1
                )

            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                    if hasattr(state, value)
                }
            )
            self._retry = 0

        except DeviceException as ex:
            await self._async_handle_update_failure(ex)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        _LOGGER.debug("Setting the fan percentage to: %s", percentage)

        if percentage == 0:
            await self.async_turn_off()
            return

        level = (
            math.ceil(
                percentage_to_ranged_value((1, FAN_2LITE_SPEED_COUNT), percentage)
            )
            - 1
        )

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )
        if self._natural_mode:
            await self._try_command(
                "Setting fan mode of the miio device failed.",
                self._device.set_mode,
                OperationModeFan2Lite.Straight,
            )
        await self._try_command(
            "Setting fan level of the miio device failed.",
            self._device.set_fan_level,
            level,
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug("Setting the preset mode to: %s", preset_mode)

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )

        mode = (
            OperationModeFan2Lite.Natural
            if preset_mode == FAN_PRESET_MODE_SLEEP
            else OperationModeFan2Lite.Straight
        )
        await self._try_command(
            "Setting fan mode of the miio device failed.",
            self._device.set_mode,
            mode,
        )

    async def async_set_natural_mode_on(self):
        """Turn the natural mode on."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFan2Lite.Natural,
        )

    async def async_set_natural_mode_off(self):
        """Turn the natural mode off."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFan2Lite.Straight,
        )


OperationModeFanP85 = OperationModeFanP70


class XiaomiFanP85(XiaomiFanP33):
    """Representation of a Xiaomi Fan P85 (Xiaomi Smart Standing Fan Pro Slim)."""

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the fan entity."""
        super().__init__(name, device, model, unique_id, retries, preset_modes_override)

        self._device_features = FEATURE_FLAGS_FAN_P85
        self._available_attributes = AVAILABLE_ATTRIBUTES_FAN_P85
        self._percentage = None
        self._preset_modes = list(FAN_PRESET_MODES_P85)
        if preset_modes_override is not None:
            self._preset_modes = preset_modes_override

        self._preset_mode = None
        self._oscillate = None
        self._natural_mode = False

        self._state_attrs = {
            ATTR_MODEL: self._model,
            **{attribute: None for attribute in self._available_attributes},
        }

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return (
            FanEntityFeature.OSCILLATE
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

    async def async_update(self):
        """Fetch state from the device."""
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._percentage = state.fan_speed
            self._oscillate = state.horizontal_swing
            self._natural_mode = state.mode == OperationModeFanP85.Natural.name
            self._state = state.power

            for preset_mode, value in FAN_PRESET_MODES_P85.items():
                if preset_mode == SPEED_OFF:
                    continue
                is_natural = preset_mode.startswith("Natural")
                if state.fan_level == value and is_natural == self._natural_mode:
                    self._preset_mode = preset_mode
                    break

            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                    if hasattr(state, value)
                }
            )
            self._retry = 0

        except DeviceException as ex:
            await self._async_handle_update_failure(ex)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug("Setting the preset mode to: %s", preset_mode)

        if preset_mode == SPEED_OFF:
            await self.async_turn_off()
            return

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )

        natural = preset_mode.startswith("Natural")
        await self._try_command(
            "Setting fan mode failed.",
            self._device.set_mode,
            OperationModeFanP85.Natural if natural else OperationModeFanP85.Straight,
        )
        await self._try_command(
            "Setting fan level of the miio device failed.",
            self._device.set_fan_level,
            FAN_PRESET_MODES_P85[preset_mode],
        )

    async def async_set_natural_mode_on(self):
        """Turn the natural mode on."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP85.Natural,
        )

    async def async_set_natural_mode_off(self):
        """Turn the natural mode off."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP85.Straight,
        )

    async def async_set_delay_off(self, delay_off_countdown: int) -> None:
        """Set delay off countdown."""
        await self._try_command(
            "Setting delay off miio device failed.",
            self._device.delay_off,
            delay_off_countdown,
        )

    async def async_set_led_brightness(self, brightness: int = 2):
        """Set LED on (brightness != 2) or off (brightness == 2)."""
        if self._device_features & FEATURE_SET_LED == 0:
            return
        await self._try_command(
            "Setting LED of the miio device failed.",
            self._device.set_light,
            brightness != 2,
        )

    async def async_turn(self, direction: str):
        """Turn fan in the given direction."""
        if self._device_features & FEATURE_TURN == 0:
            return
        await self._try_command(
            "Turning the miio device failed.",
            self._device.turn,
            direction,
        )


OperationModeFanP43 = OperationModeFanP70


class XiaomiFanP43(XiaomiFanP33):
    """Representation of a Xiaomi Fan P43 (Xiaomi Smart Standing Fan Pro Slim)."""

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the fan entity."""
        super().__init__(name, device, model, unique_id, retries, preset_modes_override)

        self._device_features = FEATURE_FLAGS_FAN_P43
        self._available_attributes = AVAILABLE_ATTRIBUTES_FAN_P43
        self._percentage = None
        self._preset_modes = list(FAN_PRESET_MODES_P43)
        if preset_modes_override is not None:
            self._preset_modes = preset_modes_override

        self._preset_mode = None
        self._oscillate = None
        self._natural_mode = False

        self._state_attrs = {
            ATTR_MODEL: self._model,
            **{attribute: None for attribute in self._available_attributes},
        }

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return (
            FanEntityFeature.OSCILLATE
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

    async def async_update(self):
        """Fetch state from the device."""
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._percentage = state.fan_speed
            self._oscillate = state.horizontal_swing
            self._natural_mode = state.mode == OperationModeFanP43.Natural.name
            self._state = state.power

            for preset_mode, value in FAN_PRESET_MODES_P43.items():
                if preset_mode == SPEED_OFF:
                    continue
                is_natural = preset_mode.startswith("Natural")
                if state.fan_level == value and is_natural == self._natural_mode:
                    self._preset_mode = preset_mode
                    break

            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                    if hasattr(state, value)
                }
            )
            self._retry = 0

        except DeviceException as ex:
            await self._async_handle_update_failure(ex)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug("Setting the preset mode to: %s", preset_mode)

        if preset_mode == SPEED_OFF:
            await self.async_turn_off()
            return

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )

        natural = preset_mode.startswith("Natural")
        await self._try_command(
            "Setting fan mode failed.",
            self._device.set_mode,
            OperationModeFanP43.Natural if natural else OperationModeFanP43.Straight,
        )
        await self._try_command(
            "Setting fan level of the miio device failed.",
            self._device.set_fan_level,
            FAN_PRESET_MODES_P43[preset_mode],
        )

    async def async_set_natural_mode_on(self):
        """Turn the natural mode on."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP43.Natural,
        )

    async def async_set_natural_mode_off(self):
        """Turn the natural mode off."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP43.Straight,
        )

    async def async_set_delay_off(self, delay_off_countdown: int) -> None:
        """Set delay off countdown."""
        await self._try_command(
            "Setting delay off miio device failed.",
            self._device.delay_off,
            delay_off_countdown,
        )

    async def async_set_led_brightness(self, brightness: int = 2):
        """Set LED on (brightness != 2) or off (brightness == 2)."""
        if self._device_features & FEATURE_SET_LED == 0:
            return
        await self._try_command(
            "Setting LED of the miio device failed.",
            self._device.set_light,
            brightness != 2,
        )

    async def async_turn(self, direction: str):
        """Turn fan in the given direction."""
        if self._device_features & FEATURE_TURN == 0:
            return
        await self._try_command(
            "Turning the miio device failed.",
            self._device.turn,
            direction,
        )


class XiaomiFanP44(XiaomiFanP33):
    """Representation of the Mijia Smart Evaporative Cooling Fan (dmaker.fan.p44)."""

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the fan entity."""
        super().__init__(name, device, model, unique_id, retries, preset_modes_override)

        self._device_features = FEATURE_FLAGS_FAN_P44
        self._available_attributes = AVAILABLE_ATTRIBUTES_FAN_P44
        self._percentage = None
        self._preset_modes = list(FAN_PRESET_MODES_P44)
        if preset_modes_override is not None:
            self._preset_modes = preset_modes_override

        self._preset_mode = None
        self._oscillate = None
        self._natural_mode = False
        self._water_tank_empty = None

        self._state_attrs = {
            ATTR_MODEL: self._model,
            **{attribute: None for attribute in self._available_attributes},
        }

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return (
            FanEntityFeature.OSCILLATE
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return FAN_P44_SPEED_COUNT

    def _warn_if_water_tank_empty(self) -> None:
        """Warn about running the evaporative cooling without water."""
        if self._water_tank_empty:
            _LOGGER.warning(
                "%s reports an empty water tank. Running the "
                "evaporative cooling without water is not recommended",
                self._name,
            )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        _LOGGER.debug("Setting the fan percentage to: %s", percentage)

        if percentage == 0:
            await self.async_turn_off()
            return

        level = math.ceil(
            percentage_to_ranged_value((1, FAN_P44_SPEED_COUNT), percentage)
        )

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )

        if self._preset_mode == FAN_PRESET_MODE_SLEEP:
            await self._try_command(
                "Setting fan mode of the miio device failed.",
                self._device.set_mode,
                OperationModeFanP44.Straight,
            )

        await self._try_command(
            "Setting fan level of the miio device failed.",
            self._device.set_fan_level,
            level,
        )

    async def async_update(self):
        """Fetch state from the device."""
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._oscillate = state.horizontal_swing
            self._natural_mode = state.mode == OperationModeFanP44.Natural.name
            was_water_tank_empty = self._water_tank_empty
            self._water_tank_empty = state.water_tank_empty
            self._state = state.power

            if (
                state.water_tank_empty
                and not was_water_tank_empty
                and state.power
                and (state.air_cooler or state.mode == OperationModeFanP44.Cold.name)
            ):
                _LOGGER.warning(
                    "%s ran out of water while the evaporative cooling is "
                    "running. Refill the water tank or switch the mode",
                    self._name,
                )

            if state.fan_level is None:
                self._percentage = None
            else:
                self._percentage = ranged_value_to_percentage(
                    (1, FAN_P44_SPEED_COUNT), state.fan_level
                )

            if state.mode == OperationModeFanP44.Sleep.name:
                self._preset_mode = FAN_PRESET_MODE_SLEEP
            elif state.mode == OperationModeFanP44.Cold.name:
                self._preset_mode = FAN_PRESET_MODE_COLD_AIR
            else:
                self._preset_mode = None
                for preset_mode, value in FAN_PRESET_MODES_P44.items():
                    if preset_mode in (
                        SPEED_OFF,
                        FAN_PRESET_MODE_SLEEP,
                        FAN_PRESET_MODE_COLD_AIR,
                    ):
                        continue
                    is_natural = preset_mode.startswith("Natural")
                    if state.fan_level == value and is_natural == self._natural_mode:
                        self._preset_mode = preset_mode
                        break

            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                    if hasattr(state, value)
                }
            )
            self._retry = 0

        except DeviceException as ex:
            await self._async_handle_update_failure(ex)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan.

        Combines level (1..4) with Straight/Natural mode, or selects a
        standalone Sleep or Cold Air mode.
        """
        _LOGGER.debug("Setting the preset mode to: %s", preset_mode)

        if preset_mode == SPEED_OFF:
            await self.async_turn_off()
            return

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )

        if preset_mode == FAN_PRESET_MODE_SLEEP:
            await self._try_command(
                "Setting fan mode failed.",
                self._device.set_mode,
                OperationModeFanP44.Sleep,
            )
            return

        if preset_mode == FAN_PRESET_MODE_COLD_AIR:
            self._warn_if_water_tank_empty()
            await self._try_command(
                "Setting fan mode failed.",
                self._device.set_mode,
                OperationModeFanP44.Cold,
            )
            return

        natural = preset_mode.startswith("Natural")
        await self._try_command(
            "Setting fan mode failed.",
            self._device.set_mode,
            OperationModeFanP44.Natural if natural else OperationModeFanP44.Straight,
        )
        await self._try_command(
            "Setting fan level of the miio device failed.",
            self._device.set_fan_level,
            FAN_PRESET_MODES_P44[preset_mode],
        )

    async def async_set_natural_mode_on(self):
        """Turn the natural mode on."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP44.Natural,
        )

    async def async_set_natural_mode_off(self):
        """Turn the natural mode off."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP44.Straight,
        )

    async def async_set_led_brightness(self, brightness: int = 2):
        """Set LED on (brightness != 2) or off (brightness == 2)."""
        if self._device_features & FEATURE_SET_LED == 0:
            return
        await self._try_command(
            "Setting LED of the miio device failed.",
            self._device.set_light,
            brightness != 2,
        )

    async def async_set_air_cooler_on(self):
        """Turn the evaporative water cooling on."""
        if self._device_features & FEATURE_SET_AIR_COOLER == 0:
            return
        self._warn_if_water_tank_empty()
        await self._try_command(
            "Setting air cooler of the miio device failed.",
            self._device.set_air_cooler,
            True,
        )

    async def async_set_air_cooler_off(self):
        """Turn the evaporative water cooling off."""
        if self._device_features & FEATURE_SET_AIR_COOLER == 0:
            return
        await self._try_command(
            "Setting air cooler of the miio device failed.",
            self._device.set_air_cooler,
            False,
        )


# Straight/Natural mode values (0/1) are identical to OperationModeFanP70.
OperationModeFanP51 = OperationModeFanP70


class XiaomiFanP51(XiaomiFanP33):
    """Representation of a Xiaomi Fan P51 (Xiaomi Smart Standing Air Circulation Fan)."""

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the fan entity."""
        super().__init__(name, device, model, unique_id, retries, preset_modes_override)

        self._device_features = FEATURE_FLAGS_FAN_P51
        self._available_attributes = AVAILABLE_ATTRIBUTES_FAN_P51
        self._percentage = None
        self._preset_modes = list(FAN_PRESET_MODES_P51)
        if preset_modes_override is not None:
            self._preset_modes = preset_modes_override

        self._preset_mode = None
        self._oscillate = None
        self._natural_mode = False

        self._state_attrs = {
            ATTR_MODEL: self._model,
            **{attribute: None for attribute in self._available_attributes},
        }

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return (
            FanEntityFeature.OSCILLATE
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

    async def async_update(self):
        """Fetch state from the device."""
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._percentage = state.fan_speed
            self._oscillate = state.horizontal_swing
            self._natural_mode = state.mode == OperationModeFanP51.Natural.name
            self._state = state.power

            for preset_mode, value in FAN_PRESET_MODES_P51.items():
                if preset_mode == SPEED_OFF:
                    continue
                is_natural = preset_mode.startswith("Natural")
                if state.fan_level == value and is_natural == self._natural_mode:
                    self._preset_mode = preset_mode
                    break

            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                    if hasattr(state, value)
                }
            )
            self._retry = 0

        except DeviceException as ex:
            await self._async_handle_update_failure(ex)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug("Setting the preset mode to: %s", preset_mode)

        if preset_mode == SPEED_OFF:
            await self.async_turn_off()
            return

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )

        natural = preset_mode.startswith("Natural")
        await self._try_command(
            "Setting fan mode failed.",
            self._device.set_mode,
            OperationModeFanP51.Natural if natural else OperationModeFanP51.Straight,
        )
        await self._try_command(
            "Setting fan level of the miio device failed.",
            self._device.set_fan_level,
            FAN_PRESET_MODES_P51[preset_mode],
        )

    async def async_set_natural_mode_on(self):
        """Turn the natural mode on."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP51.Natural,
        )

    async def async_set_natural_mode_off(self):
        """Turn the natural mode off."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP51.Straight,
        )

    async def async_set_delay_off(self, delay_off_countdown: int) -> None:
        """Set delay off countdown."""
        await self._try_command(
            "Setting delay off miio device failed.",
            self._device.delay_off,
            delay_off_countdown,
        )

    async def async_set_led_brightness(self, brightness: int = 2):
        """Set LED on (brightness != 2) or off (brightness == 2)."""
        if self._device_features & FEATURE_SET_LED == 0:
            return
        await self._try_command(
            "Setting LED of the miio device failed.",
            self._device.set_light,
            brightness != 2,
        )

    async def async_turn(self, direction: str):
        """Turn fan in the given direction."""
        if self._device_features & FEATURE_TURN == 0:
            return
        await self._try_command(
            "Turning the miio device failed.",
            self._device.turn,
            direction,
        )


class XiaomiFanLeshowSS310(XiaomiGenericDevice):
    """Representation of a Rosou SS310 Ventilator (leshow.fan.ss310)."""

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the fan entity."""
        super().__init__(name, device, model, unique_id, retries, preset_modes_override)

        self._device_features = FEATURE_FLAGS_FAN_LESHOW_SS310
        self._available_attributes = AVAILABLE_ATTRIBUTES_FAN_LESHOW_SS310
        self._preset_modes = [FAN_PRESET_MODE_SLEEP]
        if preset_modes_override is not None:
            self._preset_modes = preset_modes_override

        self._current_level = None
        self._sleep_mode = False
        self._oscillate = None
        self._vertical_oscillate = None

        self._state_attrs.update(
            {attribute: None for attribute in self._available_attributes}
        )

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return (
            FanEntityFeature.OSCILLATE
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

    async def async_update(self):
        """Fetch state from the device."""
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._oscillate = state.horizontal_swing
            self._vertical_oscillate = state.vertical_swing
            self._sleep_mode = state.mode == OperationModeFanSS310.Sleep.name
            self._state = state.power

            self._current_level = None
            for level_name, value in FAN_LEVELS_SS310.items():
                if state.fan_level == value:
                    self._current_level = level_name
                    break

            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                    if hasattr(state, value)
                }
            )
            self._retry = 0

        except DeviceException as ex:
            await self._async_handle_update_failure(ex)

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self._current_level not in FAN_SPEEDS_SS310:
            return None
        return ordered_list_item_to_percentage(FAN_SPEEDS_SS310, self._current_level)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(FAN_SPEEDS_SS310)

    @property
    def preset_modes(self):
        """Return the list of available preset modes."""
        return self._preset_modes

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        if self._state and self._sleep_mode:
            return FAN_PRESET_MODE_SLEEP
        return None

    @property
    def oscillating(self):
        """Return the oscillation state."""
        return self._oscillate

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set (horizontal) oscillation."""
        await self._try_command(
            "Setting oscillate of the miio device failed.",
            self._device.set_horizontal_oscillation,
            oscillating,
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        _LOGGER.debug("Setting the fan speed percentage to: %s", percentage)

        if percentage == 0:
            await self.async_turn_off()
            return

        level_name = percentage_to_ordered_list_item(FAN_SPEEDS_SS310, percentage)

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )

        if self._sleep_mode:
            await self._try_command(
                "Setting fan mode of the miio device failed.",
                self._device.set_mode,
                OperationModeFanSS310.Normal,
            )

        await self._try_command(
            "Setting fan level of the miio device failed.",
            self._device.set_fan_level,
            FAN_LEVELS_SS310[level_name],
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug("Setting the preset mode to: %s", preset_mode)

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )

        mode = (
            OperationModeFanSS310.Sleep
            if preset_mode == FAN_PRESET_MODE_SLEEP
            else OperationModeFanSS310.Normal
        )
        await self._try_command(
            "Setting fan mode of the miio device failed.",
            self._device.set_mode,
            mode,
        )

    async def async_set_vertical_oscillation_on(self):
        """Turn vertical oscillation on."""
        if self._device_features & FEATURE_SET_VERTICAL_OSCILLATION == 0:
            return
        await self._try_command(
            "Setting vertical oscillation on of the miio device failed.",
            self._device.set_vertical_oscillation,
            True,
        )

    async def async_set_vertical_oscillation_off(self):
        """Turn vertical oscillation off."""
        if self._device_features & FEATURE_SET_VERTICAL_OSCILLATION == 0:
            return
        await self._try_command(
            "Setting vertical oscillation off of the miio device failed.",
            self._device.set_vertical_oscillation,
            False,
        )


class XiaomiFanP28(XiaomiFanP33):
    """Representation of a Xiaomi/Mijia Fan P28 (dmaker.fan.p28)."""

    def __init__(self, name, device, model, unique_id, retries, preset_modes_override):
        """Initialize the fan entity."""
        super().__init__(name, device, model, unique_id, retries, preset_modes_override)

        self._device_features = FEATURE_FLAGS_FAN_P28
        self._available_attributes = AVAILABLE_ATTRIBUTES_FAN_P28
        self._percentage = None
        self._preset_modes = list(FAN_PRESET_MODES_P28)
        if preset_modes_override is not None:
            self._preset_modes = preset_modes_override

        self._preset_mode = None
        self._oscillate = None
        self._natural_mode = False

        self._state_attrs = {
            ATTR_MODEL: self._model,
            **{attribute: None for attribute in self._available_attributes},
        }

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return (
            FanEntityFeature.OSCILLATE
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

    async def async_update(self):
        """Fetch state from the device."""
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._percentage = state.speed
            self._oscillate = state.horizontal_swing
            self._natural_mode = state.mode == OperationModeFanP28.Natural.name
            self._state = state.power

            if state.mode == OperationModeFanP28.Sleep.name:
                self._preset_mode = FAN_PRESET_MODE_SLEEP
            else:
                self._preset_mode = None
                for preset_mode, value in FAN_PRESET_MODES_P28.items():
                    if preset_mode in (SPEED_OFF, FAN_PRESET_MODE_SLEEP):
                        continue
                    is_natural = preset_mode.startswith("Natural")
                    if state.fan_level == value and is_natural == self._natural_mode:
                        self._preset_mode = preset_mode
                        break

            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                    if hasattr(state, value)
                }
            )
            self._retry = 0

        except DeviceException as ex:
            await self._async_handle_update_failure(ex)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug("Setting the preset mode to: %s", preset_mode)

        if preset_mode == SPEED_OFF:
            await self.async_turn_off()
            return

        if not self._state:
            await self._try_command(
                "Turning the miio device on failed.", self._device.on
            )

        if preset_mode == FAN_PRESET_MODE_SLEEP:
            await self._try_command(
                "Setting fan mode failed.",
                self._device.set_mode,
                OperationModeFanP28.Sleep,
            )
            return

        natural = preset_mode.startswith("Natural")
        await self._try_command(
            "Setting fan mode failed.",
            self._device.set_mode,
            OperationModeFanP28.Natural if natural else OperationModeFanP28.Straight,
        )
        await self._try_command(
            "Setting fan level of the miio device failed.",
            self._device.set_fan_level,
            FAN_PRESET_MODES_P28[preset_mode],
        )

    async def async_set_natural_mode_on(self):
        """Turn the natural mode on."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP28.Natural,
        )

    async def async_set_natural_mode_off(self):
        """Turn the natural mode off."""
        if self._device_features & FEATURE_SET_NATURAL_MODE == 0:
            return
        await self._try_command(
            "Setting fan natural mode of the miio device failed.",
            self._device.set_mode,
            OperationModeFanP28.Straight,
        )

    async def async_set_delay_off(self, delay_off_countdown: int) -> None:
        """Set delay off countdown."""
        await self._try_command(
            "Setting delay off miio device failed.",
            self._device.delay_off,
            delay_off_countdown,
        )

    async def async_set_led_brightness(self, brightness: int = 2):
        """Set LED on (brightness != 2) or off (brightness == 2)."""
        if self._device_features & FEATURE_SET_LED == 0:
            return
        await self._try_command(
            "Setting LED of the miio device failed.",
            self._device.set_light,
            brightness != 2,
        )

    async def async_set_vertical_oscillation_on(self):
        """Turn vertical oscillation on."""
        if self._device_features & FEATURE_SET_VERTICAL_OSCILLATION == 0:
            return
        await self._try_command(
            "Setting vertical oscillation on of the miio device failed.",
            self._device.set_vertical_oscillate,
            True,
        )

    async def async_set_vertical_oscillation_off(self):
        """Turn vertical oscillation off."""
        if self._device_features & FEATURE_SET_VERTICAL_OSCILLATION == 0:
            return
        await self._try_command(
            "Setting vertical oscillation off of the miio device failed.",
            self._device.set_vertical_oscillate,
            False,
        )
