"""One-shot startup self-test that writes a diagnostic report to the HA log.

Runs once, a few seconds after a config entry finishes setting up, and only
*reads* from the device (a single status() call plus a LAN discovery
broadcast); it never sends a command. Every line carries the `SELFTEST`
marker so the whole report can be found with one search of the log, and the
report ends with a PASS/WARN/FAIL summary.

Turn it off by setting `SELFTEST_ENABLED = False` in `const.py`.

The report includes the fan's IP address and its mac-based unique_id, and
never the token. Redact those before sharing it publicly if you prefer.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from importlib.metadata import PackageNotFoundError, version
import sys
import time
import traceback
from typing import Any

from homeassistant.config_entries import ConfigEntry
import homeassistant.const as ha_const
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .log import get_logger
from .const import DOMAIN
from .discovery import broadcast_discover_device_ids
from .fan import _model_spec, get_available_attributes

_LOGGER = get_logger(__name__)

TAG = "SELFTEST"
SETTLE_SECONDS = 5

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
INFO = "INFO"


class _Report:
    """Collect report lines and tally results."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.counts = {PASS: 0, WARN: 0, FAIL: 0}

    def section(self, title: str) -> None:
        self.lines.append(f"--- {title} ---")

    def add(self, status: str, text: str) -> None:
        if status in self.counts:
            self.counts[status] += 1
        self.lines.append(f"[{status}] {text}")

    def error(self, where: str) -> None:
        """Record an unexpected exception without aborting the whole report."""
        self.counts[FAIL] += 1
        trace = traceback.format_exc().rstrip()
        self.lines.append(f"[{FAIL}] unexpected error in {where}:\n{trace}")


def _short(value: Any, limit: int = 60) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _env_section(report: _Report) -> None:
    report.section("environment")
    try:
        miio_version = version("python-miio")
    except PackageNotFoundError:
        miio_version = "unknown"
    report.add(
        INFO, f"home assistant {ha_const.__version__}, python {sys.version.split()[0]}"
    )
    report.add(INFO, f"python-miio {miio_version}")


def _entry_section(report: _Report, entry: ConfigEntry) -> None:
    runtime = entry.runtime_data
    report.section("config entry")
    report.add(
        INFO,
        f"title={entry.title!r} source={entry.source} entry_id={entry.entry_id}",
    )
    report.add(
        INFO,
        f"host={runtime.fan.ip} model={runtime.model} unique_id={runtime.unique_id}",
    )
    report.add(
        INFO,
        f"firmware={runtime.sw_version} miio_device_id={runtime.device_id} "
        f"retries={runtime.retries} "
        f"preset_override={runtime.preset_modes_override}",
    )
    report.add(
        PASS if runtime.sw_version else WARN,
        "device probe returned firmware info"
        if runtime.sw_version
        else "no firmware info (probe failed; running on the model override?)",
    )


def _model_section(report: _Report, entry: ConfigEntry) -> None:
    runtime = entry.runtime_data
    report.section("model resolution")
    spec = _model_spec(runtime.model)
    if spec is None:
        report.add(FAIL, f"model {runtime.model} has no spec")
        return
    client_cls, client_model, entity_cls = spec
    report.add(
        INFO,
        f"client class {client_cls.__name__} (wire model {client_model}), "
        f"entity class {entity_cls.__name__}",
    )
    report.add(
        PASS if isinstance(runtime.fan, client_cls) else FAIL,
        f"live client is {type(runtime.fan).__name__}",
    )
    report.add(
        PASS if type(runtime.fan_entity) is entity_cls else FAIL,
        f"live fan entity is {type(runtime.fan_entity).__name__}",
    )
    attributes = get_available_attributes(runtime.model)
    report.add(
        PASS if attributes else WARN,
        f"{len(attributes)} status attributes declared for this model",
    )


async def _device_section(
    hass: HomeAssistant, report: _Report, entry: ConfigEntry
) -> None:
    runtime = entry.runtime_data
    report.section("device round trip (read-only)")

    started = time.monotonic()
    try:
        status = await hass.async_add_executor_job(runtime.fan.status)
    except Exception as ex:
        report.add(FAIL, f"status() failed: {type(ex).__name__}: {ex}")
        return
    elapsed_ms = (time.monotonic() - started) * 1000
    report.add(
        PASS if elapsed_ms < 2000 else WARN,
        f"status() returned {type(status).__name__} in {elapsed_ms:.0f} ms",
    )

    attributes = get_available_attributes(runtime.model)
    present: list[tuple[str, Any]] = []
    missing: list[tuple[str, Any]] = []
    for raw_name in attributes.values():
        value = getattr(status, raw_name, None)
        (present if value is not None else missing).append((raw_name, value))
    report.add(
        INFO,
        "values: " + ", ".join(f"{name}={_short(value)}" for name, value in present),
    )
    report.add(
        PASS if not missing else WARN,
        f"{len(present)}/{len(attributes)} declared attributes had a value"
        + (f"; missing: {', '.join(name for name, _ in missing)}" if missing else ""),
    )

    coordinator_data = runtime.coordinator.data
    if coordinator_data is None:
        report.add(WARN, "coordinator has no data yet to compare against")
        return
    mismatches = [
        name
        for name, value in present
        if getattr(coordinator_data, name, None) != value and name not in ("use_time",)
    ]
    report.add(
        PASS if not mismatches else INFO,
        "coordinator data matches the fresh poll"
        if not mismatches
        else "coordinator differs from the fresh poll (normal if values just "
        f"changed): {', '.join(mismatches)}",
    )


def _coordinator_section(report: _Report, entry: ConfigEntry) -> None:
    coordinator = entry.runtime_data.coordinator
    report.section("coordinator")
    report.add(
        INFO,
        f"update_interval={coordinator.update_interval} "
        f"data_type={type(coordinator.data).__name__}",
    )
    report.add(
        PASS if coordinator.last_update_success else FAIL,
        "last coordinator poll succeeded"
        if coordinator.last_update_success
        else f"last coordinator poll failed: {coordinator.last_exception!r}",
    )


def _fan_entity_section(
    hass: HomeAssistant, report: _Report, entry: ConfigEntry
) -> None:
    fan = entry.runtime_data.fan_entity
    report.section("fan entity")
    report.add(INFO, f"entity_id={fan.entity_id} unique_id={fan.unique_id}")
    report.add(
        INFO,
        f"supported_features={int(fan.supported_features)} "
        f"device_features={fan._device_features} "
        f"preset_modes={fan.preset_modes}",
    )
    report.add(
        PASS if fan.available else FAIL,
        f"fan entity available={fan.available} "
        f"(retry counter={fan._retry}/{fan._retries})",
    )
    state = hass.states.get(fan.entity_id) if fan.entity_id else None
    report.add(
        PASS
        if state is not None and state.state not in ("unavailable", "unknown")
        else FAIL,
        f"HA state: {state.state if state else 'not in state machine'}",
    )
    if state is not None:
        report.add(INFO, f"state attributes: {_short(dict(state.attributes), 400)}")


def _registry_section(hass: HomeAssistant, report: _Report, entry: ConfigEntry) -> None:
    runtime = entry.runtime_data
    report.section("registries")
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    by_platform: dict[str, int] = {}
    for item in entities:
        by_platform[item.domain] = by_platform.get(item.domain, 0) + 1
    report.add(
        PASS if entities else FAIL,
        f"{len(entities)} registered entities: "
        + ", ".join(f"{k}={v}" for k, v in sorted(by_platform.items())),
    )

    unhealthy = []
    for item in entities:
        state = hass.states.get(item.entity_id)
        if item.disabled:
            continue
        if state is None or state.state in ("unavailable", "unknown"):
            unhealthy.append(f"{item.entity_id}={state.state if state else 'missing'}")
    report.add(
        PASS if not unhealthy else WARN,
        "all enabled entities have a live state"
        if not unhealthy
        else f"entities without a live state: {', '.join(unhealthy)}",
    )

    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, runtime.unique_id)}
    )
    if device is None:
        report.add(FAIL, "no device registry entry for this fan")
    else:
        report.add(
            PASS,
            f"device page: name={device.name!r} model={device.model} "
            f"sw_version={device.sw_version}",
        )
        grouped = [item for item in entities if item.device_id == device.id]
        report.add(
            PASS if len(grouped) == len(entities) else WARN,
            f"{len(grouped)}/{len(entities)} entities grouped under that device",
        )


async def _heal_section(
    hass: HomeAssistant, report: _Report, entry: ConfigEntry
) -> None:
    runtime = entry.runtime_data
    report.section("auto-heal readiness")
    protocol = getattr(runtime.fan, "_protocol", None)
    report.add(
        PASS if protocol is not None and hasattr(protocol, "ip") else FAIL,
        "python-miio exposes _protocol.ip (host can be switched in place)"
        if protocol is not None and hasattr(protocol, "ip")
        else "python-miio no longer exposes _protocol.ip; auto-heal cannot switch host",
    )
    if protocol is not None and hasattr(protocol, "ip"):
        report.add(
            PASS if protocol.ip == runtime.fan.ip else FAIL,
            f"client ip {runtime.fan.ip} and protocol ip {protocol.ip} agree",
        )
    if runtime.device_id is None:
        report.add(WARN, "no miIO device_id captured, so auto-heal is disabled")
        return

    started = time.monotonic()
    found = await hass.async_add_executor_job(broadcast_discover_device_ids)
    elapsed_ms = (time.monotonic() - started) * 1000
    report.add(
        INFO,
        f"LAN broadcast took {elapsed_ms:.0f} ms and saw {len(found)} miIO device(s)",
    )
    seen_at = found.get(runtime.device_id)
    if seen_at is None:
        report.add(
            WARN,
            "this fan did not answer the broadcast (different subnet/VLAN, a "
            "firewall, or HA in a container without host networking); "
            "auto-heal will not work, use Reconfigure if the IP changes",
        )
    else:
        report.add(
            PASS if seen_at == runtime.fan.ip else WARN,
            f"broadcast found this fan at {seen_at} (configured host {runtime.fan.ip})",
        )


def _services_section(hass: HomeAssistant, report: _Report) -> None:
    report.section("services")
    services = hass.services.async_services().get(DOMAIN, {})
    report.add(
        PASS if services else FAIL,
        f"{len(services)} services registered under {DOMAIN}",
    )


async def async_run_selftest(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Run every check and log the combined report once."""
    await asyncio.sleep(SETTLE_SECONDS)

    report = _Report()
    steps: list[tuple[str, Callable[[], None]]] = [
        ("environment", lambda: _env_section(report)),
        ("config entry", lambda: _entry_section(report, entry)),
        ("model resolution", lambda: _model_section(report, entry)),
        ("coordinator", lambda: _coordinator_section(report, entry)),
        ("fan entity", lambda: _fan_entity_section(hass, report, entry)),
        ("registries", lambda: _registry_section(hass, report, entry)),
        ("services", lambda: _services_section(hass, report)),
    ]
    async_steps: list[tuple[str, Callable[[], Awaitable[None]]]] = [
        ("device round trip", lambda: _device_section(hass, report, entry)),
        ("auto-heal readiness", lambda: _heal_section(hass, report, entry)),
    ]

    for name, step in steps:
        try:
            step()
        except Exception:
            report.error(name)
    for async_name, async_step in async_steps:
        try:
            await async_step()
        except Exception:
            report.error(async_name)

    counts = report.counts
    summary = (
        f"SUMMARY: {counts[PASS]} passed, {counts[WARN]} warnings, "
        f"{counts[FAIL]} failures"
    )
    body = "\n".join(f"{TAG} {line}" for line in [*report.lines, summary])
    _LOGGER.info(
        "%s begin (%s)\n%s\n%s end",
        TAG,
        entry.title,
        body,
        TAG,
    )
