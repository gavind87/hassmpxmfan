# Xiaomi Mi Smart Pedestal Fan

A Home Assistant integration for Xiaomi and Mijia smart fans, controlled locally over the miIO protocol. Current version: **1.0.0**.

## Supported devices

| Name                        | Model                  | Model no. | Specs |
| ----------------------------| ---------------------- | --------- | ----- |
| Pedestal Fan Fan V2         | zhimi.fan.v2           | | |
| Pedestal Fan Fan V3         | zhimi.fan.v3           | | |
| Pedestal Fan Fan SA1        | zhimi.fan.sa1          | | |
| Pedestal Fan Fan ZA1        | zhimi.fan.za1          | | |
| Pedestal Fan Fan ZA3        | zhimi.fan.za3          | | |
| Pedestal Fan Fan ZA4        | zhimi.fan.za4          | ZLBPLDS04ZM | |
| Smartmi Standing Fan 3      | zhimi.fan.za5          | | |
| Pedestal Fan Fan 1C         | dmaker.fan.1c          | | |
| Pedestal Fan Fan P5         | dmaker.fan.p5          | | |
| Pedestal Fan Fan P8         | dmaker.fan.p8          | | |
| Pedestal Fan Fan P9         | dmaker.fan.p9          | | |
| Pedestal Fan Fan P10        | dmaker.fan.p10         | | |
| Mijia Pedestal Fan          | dmaker.fan.p11         | BPLDS03DM  | 2800mAh, 24W, <=58dB  |
| Smart Standing Fan 2 Pro    | dmaker.fan.p33         | BPLDS03DM  | 2800mAh, 24W, <=58dB  |
| Pedestal Fan Fan P15        | dmaker.fan.p15         | | |
| Mi Smart Standing Fan 2 P18 | dmaker.fan.p18         | BPLDS02DM  | AC, 15W, 30.2-55.8dB  |
| Mi Smart Standing Fan 2 P30 | dmaker.fan.p30         | BPLDS02DM  | AC, 15W, 30.2-55.8dB  |
| Rosou SS4 Ventilator        | leshow.fan.ss4         | | |
| Xiaomi Smart Tower Fan      | dmaker.fan.p39         | BPTS01DM | 22W, <=63dB |
| Xiaomi Smart Standing Air Circulation Fan | xiaomi.fan.p76 | JLLDS01XY | - |
| Xiaomi Smart Desktop Air Circulation Fan  | xiaomi.fan.p70 | - | - |
| Mi Smart Standing Fan 2 Lite              | xiaomi.fan.2lite | - | - |
| Xiaomi Smart Standing Fan Pro Slim        | xiaomi.fan.p85 | - | - |
| Xiaomi Smart Standing Fan Pro Slim 2       | xiaomi.fan.p43 | - | - |
| Mijia Smart Evaporative Cooling Fan | dmaker.fan.p44 | - | - |
| Xiaomi Smart Standing Air Circulation Fan / Mijia Circulation Fan | xiaomi.fan.p51 | - | - |
| Rosou SS310 Ventilator | leshow.fan.ss310 | - | - |
| Mijia Fan | dmaker.fan.p28 | - | - |


## Features

### Pedestal Fan

* Power (on, off)
* Preset modes (Level 1, Level 2, Level 3, Level 4)
* Speed percentage (0...100)
* Oscillate (on, off)
* Oscillation angle (30, 60, 90, 120, 140, 150)
* Natural mode (on, off)
* Rotate by 5 degrees (left, right)
* Child lock (on, off)
* LED brightness (bright, dim, off)
* Attributes
  - model
  - temperature (zhimi.fan.v2 and v3 only)
  - humidity (zhimi.fan.v2 and v3 only)
  - led_brightness
  - buzzer
  - child_lock
  - natural_level
  - oscillate
  - delay_off_countdown
  - speed
  - direct_speed
  - natural_speed
  - angle
  - use_time
  - ac_power
  - battery (zhimi.fan.v2 and v3 only)
  - battery_charge (zhimi.fan.v2 & v3 only)
  - button_pressed (zhimi.fan.v2 & v3 only)
  - led (zhimi.fan.v2 only)
  - battery_state (zhimi.fan.v2 only)
  - anion (zhimi.fan.za5 only)


### Rosou SS4 Ventilator (leshow.fan.ss4)

* Power (on, off)
* Operation modes (manual, sleep, strong, natural)
* Preset modes (Level 1, Level 2, Level 3, Level 4)
* Speed percentage (0...100)
* Oscillate (on, off)
* Buzzer (on, off)
* Delayed turn off (minutes)

* Attributes
  - `model`
  - `mode`
  - `speed`
  - `buzzer`
  - `oscillate`
  - `delay_off_countdown`
  - `error_detected`


## Install

You can install this custom component via [HACS](https://hacs.xyz/). Search for 'Xiaomi Mi Smart Pedestal Fan Integration' at the integration page of HACS. Alternatively, you can install it manually by copying the custom_components folder to your Home Assistant configuration folder. A restart of Home Assistant is required afterwards.

## Setup

### From the UI (recommended)

Go to **Settings > Devices & Services > Add Integration** and search for "Xiaomi Mi Smart Pedestal Fan". Enter the host/IP and API token (see above for how to get the token); leave the model on auto-detect unless your device doesn't reliably answer the generic info probe. The fan is added as its own Device, with the model/manufacturer/firmware shown on its device page, and `retries`/`preset_modes_override` can be tuned afterwards from the integration's **Configure** button.

### From configuration.yaml (legacy, still supported)

```yaml
# configuration.yaml

fan:
  - platform: xiaomi_miio_fan
    name: Xiaomi Smart Fan
    host: 192.168.130.71
    token: b7c4a758c251955d2c24b1d9e41ce47d
```

Configuration variables:
- **host** (*Required*): The IP of your fan.
- **token** (*Required*): The API token of your fan.
- **name** (*Optional*): The name of your fan.
- **model** (*Optional*): The model of your device. This setting can be used to bypass the device model detection and is recommended if your device isn't always available.
- **preset_modes_override** (*Optional*): Overrides the list of preset modes. Can be used to suppress the preset mode switches at homekit by passing an empty list (`preset_modes_override: []`).

YAML entries are imported into a config entry automatically on startup (once), so they show up and can be managed under **Settings > Devices & Services** too. You can remove the YAML block once the import has happened if you'd rather manage the fan entirely from the UI.

### When a fan's IP address changes

If a fan's IP changes (a new DHCP lease, a router reboot) and it stops responding, the integration will scan the local network for it by its stable miIO device ID and switch to the new address automatically, logging what it found. This only works within the same broadcast domain/subnet as Home Assistant. If a fan moves to a different network, or its token changed, use the integration's **Reconfigure** option (on its entry under Settings > Devices & Services) to update the host/token by hand.

### Migrating from the earlier YAML-only setup

If your YAML entry did **not** set `model:` (the common case), nothing changes: the fan keeps the exact same entity it always had, now additionally grouped under its own device page. If you *did* set `model:` explicitly, that fan previously had no stable unique ID at all (a long-standing bug) - after upgrading it will get one for the first time, which Home Assistant will treat as a new entity. Re-apply any customizations (friendly name, area, automations) to the new entity, or remove `model:` from your YAML so auto-detection can recover the original identity.

## Monitoring entities

Besides the `fan` entity, each device also gets read-only sensor/binary sensor entities for whichever of the following its model actually exposes (most models only expose a few of these):

- **Sensors**: temperature, humidity, use time, battery state, battery charging state, last button pressed.
- **Binary sensors**: water tank empty, error detected, AC power.

These share one poller (so they don't add extra network traffic per entity) and go unavailable rather than needing their own retry handling. The fan entity itself still polls separately and handles its own retries/IP auto-heal, as described above.

## Switches

Fans that support them also get switch entities for: buzzer, child lock, the ionizer (ZA5), and evaporative cooling (P44). These delegate to the exact same command logic the `fan` entity itself uses, so they stay in sync with it.

Natural mode, oscillation angle, delay-off, and LED brightness are *not* exposed as entities (yet) - those turned out to have real per-model differences in units/semantics that need resolving one model at a time rather than exposed uniformly. They remain available as services (see below).

## Platform services

#### Service `fan.set_percentage`

Set the fan speed percentage.

| Service data attribute    | Optional | Description                                                                |
|---------------------------|----------|----------------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific fan entity. Else targets all.                       |
| `percentage`              |       no | Percentage speed setting. Valid values are between 0 and 100.              |

#### Service `fan.set_preset_mode`

Set a preset mode.

| Service data attribute    | Optional | Description                                                                  |
|---------------------------|----------|------------------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific fan entity. Else targets all.                         |
| `preset_mode`             |       no | Preset mode. Valid values are `Level 1`, `Level 2`, `Level 3` and `Level 4`. |

#### Service `fan.oscillate`

Oscillates the fan.

| Service data attribute    | Optional | Description                                                           |
|---------------------------|----------|-----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific fan entity. Else targets all.                  |
| `oscillating`             |       no | Flag to turn on/off oscillation. Valid values are `True` and `False`. |

#### Service `fan.set_direction`

Rotates the fan 5 degrees to the left/right.

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific fan entity. Else targets all.                 |
| `direction`               |       no | Rotate the fan 5 degrees. Valid values are `left`/`reverse` and `right`/`forward`.       |

#### Service `xiaomi_miio_fan.fan_set_oscillation_angle`

Set the oscillation angle. Supported values are 30, 60, 90 and 120 degrees.

| Service data attribute    | Optional | Description                                                            |
|---------------------------|----------|------------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.           |
| `angle`                   |       no | Angle in degrees. Valid values are `30`, `60`, `90`, `120`, and `140`. |

#### Service `xiaomi_miio_fan.fan_set_delay_off`

Set the scheduled turn off time. Supported values are 0, 60, 120, 180, 240, 300, 360, 420, 480 minutes. When 0 is passed, delay_off is disabled.


| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.         |
| `delay_off_countdown`     |       no | Time in minutes. Valid values are `0`, `60`, `120`, `180`, `240`, `300`, `360`, `420`, `480` minutes. |

#### Service `xiaomi_miio_fan.fan_set_natural_mode_on`

Turn the natural mode on.

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.         |

#### Service `xiaomi_miio_fan.fan_set_natural_mode_off`

Turn the natural mode off.

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.         |

#### Service `xiaomi_miio_fan.fan_set_buzzer_on`

Turn the buzzer on.

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.         |

#### Service `xiaomi_miio_fan.fan_set_buzzer_off`

Turn the buzzer off.

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.         |

#### Service `xiaomi_miio_fan.fan_set_child_lock_on`

Turn the child lock on.

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.         |

#### Service `xiaomi_miio_fan.fan_set_child_lock_off`

Turn the child lock off.

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.         |

#### Service `xiaomi_miio_fan.fan_set_led_brightness`

Set the led brightness. Supported values are 0 (Bright), 1 (Dim), 2 (Off).

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.         |
| `brightness`              |       no | Brightness, between 0 and 2.                                         |

#### Service `xiaomi_miio_fan.fan_set_anion_on`

Turn the ionizer on.

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.         |

#### Service `xiaomi_miio_fan.fan_set_anion_off`

Turn the ionizer off.

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.         |

#### Service `xiaomi_miio_fan.fan_set_air_cooler_on`

Turn the evaporative water cooling on. (P44 only)

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.         |

#### Service `xiaomi_miio_fan.fan_set_air_cooler_off`

Turn the evaporative water cooling off. (P44 only)

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.         |

#### Service `xiaomi_miio_fan.fan_turn`

Turn to the given direction. Supported values are `left` and `right`, plus `up` and `down` on P70 and P76. (P30, P45, P70, P76, P85, P43, and P51)

| Service data attribute | Optional | Description                                                                          |
|------------------------|----------|--------------------------------------------------------------------------------------|
| `entity_id`            | yes      | Only act on a specific xiaomi miio entity. Else targets all.                         |
| `direction`            | no       | Direction. Valid values are `left` and `right`; `up` and `down` only on P70 and P76. |

#### Service `xiaomi_miio_fan.fan_set_vertical_oscillation_on`

Turn the vertical oscillation on. (P70, P76, SS310 and P28 only)

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.         |

#### Service `xiaomi_miio_fan.fan_set_vertical_oscillation_off`

Turn the vertical oscillation off. (P70, P76, SS310 and P28 only)

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.         |

#### Service `xiaomi_miio_fan.fan_set_vertical_oscillation_angle`

Set the vertical oscillation angle. (P70, P76 and P28 only)

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.         |
| `vertical_angle`          |       no | Vertical angle in degrees. Valid values are `30`, `60`, `90` and `100`. |
