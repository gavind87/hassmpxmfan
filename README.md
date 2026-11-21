# Xiaomi Mi Smart Pedestal Fan

Home Assistant integration for Xiaomi/Mijia smart fans, controlled locally over miIO (no cloud). Version **1.5.1**, stable and running in production. No further work is planned unless something major comes up (a new model, a Home Assistant breaking change, or polling problems).

A modernized fork of [syssi/xiaomi_fan](https://github.com/syssi/xiaomi_fan) (Sebastian Muszynski, Apache 2.0); `fan.py` is still largely derived from it. See [NOTICE](NOTICE).

## Features

- **UI setup**: add a fan from **Settings > Devices & Services** with its host and token. The model is auto-detected. A **Reconfigure** step fixes a changed host or token.
- **Device pages**: every fan is a proper device with manufacturer, model and firmware, and all its entities grouped under it.
- **Automatic IP recovery**: if a fan stops answering (DHCP change, router reboot), the integration finds its new address by its miIO device ID and switches over by itself.
- **Legacy YAML import**: existing `fan:` YAML entries are imported into a config entry automatically.
- **Diagnostics and repairs**: a redacted "Download diagnostics" button on the device page, and a repair notice while an imported YAML block is still present.
- **Startup self-test**: a read-only report in the HA log to help debug a new or misbehaving fan.
- **Wide model support**: 28 models across the zhimi, dmaker, xiaomi and leshow families (list below).
- **Tested**: a pytest suite and CI cover model mapping, config flow, IP recovery and the update path.

## Install

Copy `custom_components/xiaomi_miio_fan` into the HA config folder (or add this repo to HACS as a custom repository) and restart HA. Then **Settings > Devices & Services > Add Integration > Xiaomi Mi Smart Pedestal Fan**: enter host and token, and leave model on auto-detect unless the fan doesn't answer the info probe reliably. `retries` and `preset_modes_override` can be changed from **Configure**.

Legacy YAML still works and is imported into a config entry once on startup (the YAML block can then be removed):

```yaml
fan:
  - platform: xiaomi_miio_fan
    host: 192.168.130.71
    token: <token>
    # name, model, preset_modes_override are optional
```

If a YAML entry sets `model:`, the fan gets a stable unique ID for the first time on import, which HA treats as a new entity.

## Supported models

- **zhimi**: fan.v2, v3, sa1, za1, za3, za4, za5
- **dmaker**: fan.1c, p5, p8, p9, p10, p11, p15, p18, p28, p30, p33, p39, p44
- **xiaomi**: fan.p30, p43, p45, p51, p70, p76, p85, 2lite
- **leshow**: fan.ss4, ss310

Not every entity below exists on every model; each fan only gets the ones it actually supports.

## Entities

| Platform | Entities | Notes |
| -------- | -------- | ----- |
| `fan` | Power, preset modes, speed percentage, oscillation, direction | Plus model-dependent attributes (temperature/humidity on v2/v3, ionizer on ZA5, etc.) |
| `sensor` | Temperature, humidity, use time, battery state, battery charge, last button pressed | Where the model reports them |
| `binary_sensor` | Water tank empty, error detected, AC power | Where the model reports them |
| `switch` | Buzzer, child lock, LED, ionizer (ZA5), evaporative cooling (P44) | Use the same command logic as the fan entity |
| `number` | Turn-off timer (minutes, 0 cancels) | Value is the last one set from HA; the device doesn't report a reliable countdown |
| `select` | Oscillation angle | Options are exactly the angles each model accepts. Zhimi fans offer 30/60/90/120 |
| `button` | Rotate left, rotate right | Zhimi and P5 turn the head 5 degrees per press; P30, P43, P45, P51, P70, P76 and P85 use their turn command |

Kept as services only: natural mode, multi-level LED brightness, vertical oscillation and the 1C's oscillation angle (its client has no angle command).

## Tokens and recovery

Each fan has a 32-character hex token that the integration needs to talk to it. Mi Home doesn't show it. Common ways to get it are the cloud-login step of Home Assistant's built-in Xiaomi Miio integration (it lists the tokens for your account's devices) or the community `Xiaomi-cloud-tokens-extractor` tool. Keep a copy of each fan's token somewhere safe.

The token **changes** whenever a fan is factory-reset or removed and re-added in the Mi Home app. If a fan suddenly stays unavailable and its IP is fine, this is the likely cause:

1. Get the fan's new token (as above).
2. In HA, open **Settings > Devices & Services > Xiaomi Mi Smart Pedestal Fan**, use **Reconfigure** on that entry, and enter the new token (and host, if it moved).
3. The entry reloads and the fan comes back with its existing entities and history, because they're tied to the fan's MAC address, not its token.

If the fan is on a different subnet or VLAN from Home Assistant, automatic IP recovery can't find it; reconfigure the host by hand.

## IP changes

If a fan stops responding after repeated polls, the integration broadcasts on the LAN for its miIO device ID and switches to the new address automatically (same subnet only, 5 minute cooldown between scans). If the fan is on another network or its token changed, use **Reconfigure** on the entry.

## Startup self-test

A read-only diagnostic report is written to the HA log shortly after setup (one `status()` call plus a discovery broadcast, never a command). Search the log for `SELFTEST`. Disable with `SELFTEST_ENABLED = False` in `const.py`. All log output is tagged `[XIAOMI_MIIO_FAN]`.

## Services

Standard `fan.*` services: `set_percentage`, `set_preset_mode`, `oscillate`, `set_direction`.

Custom `xiaomi_miio_fan.*` services (all take an optional `entity_id`):

| Service | Data | Notes |
| ------- | ---- | ----- |
| `fan_set_oscillation_angle` | `angle`: 30, 60, 90, 120, 140 | |
| `fan_set_delay_off` | `delay_off_countdown`: 0, 60, 120 ... 480 (minutes) | 0 disables |
| `fan_set_natural_mode_on` / `_off` | | |
| `fan_set_buzzer_on` / `_off` | | |
| `fan_set_child_lock_on` / `_off` | | |
| `fan_set_led_brightness` | `brightness`: 0 bright, 1 dim, 2 off | |
| `fan_set_raw_led_brightness` | raw device value | |
| `fan_set_anion_on` / `_off` | | ZA5 |
| `fan_set_air_cooler_on` / `_off` | | P44 |
| `fan_turn` | `direction`: left, right (up, down on P70/P76) | P30, P45, P70, P76, P85, P43, P51 |
| `fan_set_vertical_oscillation_on` / `_off` | | P70, P76, SS310, P28 |
| `fan_set_vertical_oscillation_angle` | `vertical_angle`: 30, 60, 90, 100 | P70, P76, P28 |

## Known limitations

- **Two pollers per fan.** The fan entity polls the device on its own, and the sensors share a separate coordinator poll. This roughly doubles the (tiny) status traffic to each fan. Merging them was evaluated and deliberately not done: the gain is small and it would rewrite the polling path the deployed fans rely on. It would only be worth doing if timeouts or fans flapping to unavailable show up.
- **IP recovery is same-subnet only.** It relies on a LAN broadcast.
- **DHCP discovery for initial setup** is not implemented; add fans by host and token.
- Verified on real hardware with three zhimi fans (ZA1, ZA1, ZA4) and one dmaker 1C. Other models are covered by the test suite and the original upstream behaviour, not by hands-on testing.
