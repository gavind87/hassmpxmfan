"""The Xiaomi Mi Smart Pedestal Fan integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from miio import Device, DeviceException

from .const import (
    CONF_MODEL,
    CONF_PRESET_MODES_OVERRIDE,
    CONF_RETRIES,
    DATA_KEY,
    DEFAULT_NAME,
    DEFAULT_RETRIES,
)
from .coordinator import XiaomiMiioFanDataUpdateCoordinator
from .fan import _build_device, build_fan_client
from .runtime import XiaomiMiioFanRuntimeData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.FAN,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Xiaomi Mi Smart Pedestal Fan from a config entry.

    Connecting to the device, picking its model, and building the shared
    miio client all happen here, once, *before* any platform is forwarded -
    so the fan entity and the monitoring entities (sensor/binary_sensor) all
    share the exact same client object and coordinator instead of each
    connecting independently. Platforms are set up concurrently
    (`async_forward_entry_setups` uses `asyncio.gather`), so this can't be
    split across them without risking a race.
    """
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    config = {**entry.data, **entry.options}
    host = config[CONF_HOST]
    token = config[CONF_TOKEN]
    name = config.get(CONF_NAME, DEFAULT_NAME)
    model_override = config.get(CONF_MODEL)
    retries = config.get(CONF_RETRIES, DEFAULT_RETRIES)
    preset_modes_override = config.get(CONF_PRESET_MODES_OVERRIDE)

    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    # Probe the device once so every fan gets a stable mac-based unique_id, a
    # device registry entry with real firmware/hardware info, and the miIO
    # device ID used later to re-locate it if its IP address changes. When a
    # model override is configured, a failed probe isn't fatal (that's
    # exactly what the override is for: devices whose generic info() call is
    # unreliable) - fall back to a host-based unique_id and continue anyway.
    model = model_override
    unique_id = None
    sw_version = None
    device_id = None
    try:
        miio_device = Device(host, token)
        device_info = await hass.async_add_executor_job(miio_device.info)
        model = model_override or device_info.model
        unique_id = f"{model}-{device_info.mac_address}"
        sw_version = device_info.firmware_version
        # The info() call above already performed a handshake, so this is a
        # free, synchronous read of the miIO device ID - the stable
        # fingerprint used later to re-locate the device if its IP changes.
        device_id = miio_device.device_id
        _LOGGER.info(
            "%s %s %s detected",
            device_info.model,
            device_info.firmware_version,
            device_info.hardware_version,
        )
    except DeviceException as ex:
        if model_override is None:
            raise ConfigEntryNotReady(f"Unable to connect to {host}: {ex}") from ex
        _LOGGER.warning(
            "Could not probe %s for firmware/mac info, continuing with the "
            "configured model %s: %s",
            host,
            model_override,
            ex,
        )
        unique_id = f"{model_override}-{host}"

    # model is only ever None here if model_override was None too, in which
    # case the except branch above already raised - this just makes that
    # invariant explicit for the type checker.
    assert model is not None
    fan_client = build_fan_client(host, token, model)
    if fan_client is None:
        # Not a transient failure - retrying won't make an unknown model
        # supported, so this is a hard error rather than ConfigEntryNotReady.
        raise ConfigEntryError(f"Unsupported fan model '{model}'.")

    fan_entity = _build_device(
        fan_client, model, name, unique_id, retries, preset_modes_override
    )
    if fan_entity is None:
        # build_fan_client() above already returned None for the same model
        # otherwise, so this is unreachable - but guard anyway rather than
        # trust that the two functions' model matching can never drift apart.
        raise ConfigEntryError(f"Unsupported fan model '{model}'.")
    fan_entity.sw_version = sw_version
    fan_entity._device_id = device_id

    coordinator = XiaomiMiioFanDataUpdateCoordinator(hass, fan_client, name)
    # A plain, non-raising refresh rather than async_config_entry_first_refresh():
    # when a model override is configured, a device that's unreachable right
    # now must not block the fan entity from being created at all (that's the
    # same tolerance the probe above already has for exactly that case). The
    # monitoring entities will just start unavailable and pick up data on the
    # coordinator's next successful poll.
    await coordinator.async_refresh()

    entry.runtime_data = XiaomiMiioFanRuntimeData(
        fan=fan_client,
        fan_entity=fan_entity,
        coordinator=coordinator,
        model=model,
        name=name,
        unique_id=unique_id,
        device_id=device_id,
        sw_version=sw_version,
        retries=retries,
        preset_modes_override=preset_modes_override,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hass.data.get(DATA_KEY, {}).pop(entry.entry_id, None)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
