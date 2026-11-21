# Roadmap (draft)

Status of `custom_components/xiaomi_miio_fan`. Phases 1-3 (config flow, device
registry, IP auto-heal, coordinator, sensor/binary_sensor/switch entities) are
done and deployed. This covers what remains.

## Phase 4 - Low-risk cleanup (no behavior change)

Safe to ship without hardware testing; verify with ruff, mypy, pyflakes.

- [x] Added `_async_set_feature` helper; buzzer / child-lock pairs collapsed.
      Per-model natural-mode pairs are left for Phase 6 (messages/enums differ).
- [x] Type `XiaomiMiioFanRuntimeData` properly (`fan`, `fan_entity`,
      `coordinator` are `Any` today).
- [x] Replace `assert model is not None` in `__init__.py` with a real raise.
- [x] `hass.data[DATA_KEY]` is NOT a leftover (fan.py services use it); kept.
- [x] Add a cooldown (about 5 min) to `_async_try_heal_host` so an offline fan
      doesn't broadcast on the LAN every poll cycle.
- [x] Guard `self._device._protocol.ip = ...` with a guarded or public path so
      a python-miio upgrade can't break heal silently.

## Phase 5 - Tests

Do this before Phase 6, since it makes the refactor safe.

- [x] Add `tests/` with pytest + `pytest-homeassistant-custom-component`.
- [x] Cover `_model_spec` (every supported model resolves), config flow
      (user, import; reconfigure still to add) and heal logic (mocked discovery).
- [x] Add a CI job running pytest next to hassfest / mypy / pre-commit.

Written but not yet run (no local Home Assistant install); first CI run is the real check.

## Phase 6 - Consolidate `fan.py` (about 6.7k lines)

- [ ] Move model-specific `FanStatusXXX` / `FanXXX` MIoT classes and enums into
      their own module(s); `fan.py` keeps entities only.
- [ ] Define a per-model declarative field map (percentage, oscillate, natural
      mode, preset logic) and one shared `async_update` on the base class.
      Delete the ~18 per-class copies.
- [ ] Keep preset-mode logic as an overridable hook (P76 and others differ).

## Phase 7 - Single poller (fix double polling)

Needs real-hardware testing; deploy to one fan first.

- [ ] Move the fan entity onto `XiaomiMiioFanDataUpdateCoordinator`
      (`CoordinatorEntity`, `should_poll = False`).
- [ ] Move retry-tolerance and auto-heal into the coordinator's
      `_async_update_data`; keep the post-command `_skip_update` behavior via
      `async_set_updated_data`.
- [ ] Remove the double-polling and thread-safety caveat from the docstring.

## Phase 8 - More entities

Needs a model-by-model unit/semantics check first (not a blind generic pass).

- [ ] `number`: oscillation angle, delay-off (normalize minutes vs. non-minutes
      across the base `XiaomiFan` family and `XiaomiFanP5`+ subclasses).
- [ ] `select`: LED brightness, natural mode.

## Phase 9 - Polish

- [ ] `diagnostics.py` (download-diagnostics, with token/host redacted).
- [ ] Repair issue prompting removal of the YAML block once imported.
- [ ] DHCP discovery trigger for initial setup.

## Suggested order

4 -> 5 -> 6 -> 7 -> 8 -> 9. Phases 6 and 7 are the high-value, high-risk pair;
tests (Phase 5) are the gate for both.
