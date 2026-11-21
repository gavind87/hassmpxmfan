# Xiaomi Mi Smart Pedestal Fan

Personal Home Assistant integration for Xiaomi/Mijia smart fans, controlled locally over miIO. Version **1.3.0**.

A modernized fork of [syssi/xiaomi_fan](https://github.com/syssi/xiaomi_fan) (Sebastian Muszynski, Apache 2.0); `fan.py` is still largely derived from it. See [NOTICE](NOTICE).

## Status

| Phase | What | State |
| ----- | ---- | ----- |
| 1 | Config flow, YAML import, reconfigure step, device pages, IP auto-heal, shared retry/heal logic | Done, running on real HA |
| 2 | `DataUpdateCoordinator` + shared runtime data; `sensor` / `binary_sensor` entities | Done |
| 3 | `switch` entities (buzzer, child lock, ionizer, evaporative cooling) | Done |
| 4 | Cleanup: command helper, typed runtime data, heal cooldown (~5 min), guarded host update | Done |
| 5 | pytest suite (model spec, config flow, heal) + CI job; startup self-test | Done, released and running in prod |
| 6 | Split `fan.py`: MIoT device/status classes moved into `miot/`; the ~18 copied `async_update` methods collapsed into one base-class template with a per-model `_apply_state` hook | Done, unreleased (not yet tried on hardware) |
| 7 | Single poller: move the fan entity onto the coordinator (fixes double polling); retry/heal move into the coordinator. Needs hardware testing on one fan first | Planned |
| 8 | `number` (turn-off timer), `select` (oscillation angle) and LED `switch`. Unit audit done: every client takes minutes except zhimi and ZA5, which the entity already converts. Multi-level LED brightness and natural mode stay service-only | Done (untested on hardware) |
| 9 | `diagnostics.py` (token/host/MAC redacted) and a repair issue to remove the imported YAML block: done, unreleased. DHCP discovery: planned | Partly done |

Order: 6 -> 7 -> 8 -> 9. Tests are the gate for the 6/7 refactors.

## Install and setup

Copy `custom_components/xiaomi_miio_fan` into the HA config folder (or add this repo to HACS as a custom repository) and restart HA. Then **Settings > Devices & Services > Add Integration > Xiaomi Mi Smart Pedestal Fan**: enter host and token, leave model on auto-detect unless the fan doesn't answer the info probe reliably. `retries` and `preset_modes_override` can be changed from **Configure**.

Legacy YAML still works and is imported into a config entry once on startup (the YAML block can then be removed):

```yaml
fan:
  - platform: xiaomi_miio_fan
    host: 192.168.130.71
    token: <token>
    # name, model, preset_modes_override are optional
```

If a YAML entry sets `model:`, the fan gets a stable unique ID for the first time on import, which HA treats as a new entity.

### IP changes

If a fan stops responding after repeated polls, the integration broadcasts on the LAN for its miIO device ID and switches to the new address automatically (same subnet only, 5 min cooldown). If it's on another network or the token changed, use **Reconfigure** on the entry.

### Startup self-test

A read-only diagnostic report is written to the HA log shortly after setup (one `status()` call plus a discovery broadcast, never a command). Search the log for `SELFTEST`. Disable with `SELFTEST_ENABLED = False` in `const.py`. All log output is tagged `[XIAOMI_MIIO_FAN]`.

## Supported models

zhimi.fan.v2, v3, sa1, za1, za3, za4, za5 · dmaker.fan.1c, p5, p8, p9, p10, p11, p15, p18, p28, p30, p33, p39, p44 · leshow.fan.ss4, ss310 · xiaomi.fan.p43, p51, p70, p76, p85, 2lite

## Entities

- **fan**: power, preset modes (Level 1-4), speed percentage, oscillation, direction (5 degree rotate), plus model-dependent attributes (temperature/humidity on v2/v3, anion on za5, etc.).
- **Sensors** (where the model exposes them): temperature, humidity, use time, battery state, battery charging state, last button pressed.
- **Binary sensors**: water tank empty, error detected, AC power.
- **Switches**: buzzer, child lock, ionizer (ZA5), evaporative cooling (P44). These call the same command logic as the fan entity.

- **Diagnostics**: Download diagnostics on the device page (host, token, MAC and device ID redacted).
- **Repairs**: while a legacy YAML block is still present, a repair notice asks you to remove it.

Sensors share one coordinator poller; the fan entity still polls on its own (see Phase 7). Natural mode, oscillation angle, delay-off and LED brightness are services only until Phase 8.

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
| `fan_set_anion_on` / `_off` | | ZA5 |
| `fan_set_air_cooler_on` / `_off` | | P44 |
| `fan_turn` | `direction`: left, right (up, down on P70/P76) | P30, P45, P70, P76, P85, P43, P51 |
| `fan_set_vertical_oscillation_on` / `_off` | | P70, P76, SS310, P28 |
| `fan_set_vertical_oscillation_angle` | `vertical_angle`: 30, 60, 90, 100 | P70, P76, P28 |
