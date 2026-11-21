"""Config flow for the Xiaomi Mi Smart Pedestal Fan integration."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from miio import Device, DeviceException
import voluptuous as vol

from .log import get_logger
from .const import (
    CONF_MODEL,
    CONF_PRESET_MODES_OVERRIDE,
    CONF_RETRIES,
    DEFAULT_NAME,
    DEFAULT_RETRIES,
    DOMAIN,
    SUPPORTED_MODELS,
)

_LOGGER = get_logger(__name__)

AUTO_DETECT_MODEL = "auto"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Optional(CONF_MODEL, default=AUTO_DETECT_MODEL): vol.In(
            [AUTO_DETECT_MODEL, *SUPPORTED_MODELS]
        ),
    }
)


async def _async_get_device_info(hass: HomeAssistant, host: str, token: str):
    """Connect to the device and return its miio info, raising on failure."""
    device = Device(host, token)
    return await hass.async_add_executor_job(device.info)


class XiaomiMiioFanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for the Xiaomi Mi Smart Pedestal Fan."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step where a user adds a fan from the UI."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            token = user_input[CONF_TOKEN]
            name = user_input.get(CONF_NAME, DEFAULT_NAME)
            model = user_input.get(CONF_MODEL)
            if model == AUTO_DETECT_MODEL:
                model = None

            try:
                await _async_get_device_info(self.hass, host, token)
            except DeviceException:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"{DOMAIN}-{host}")
                self._abort_if_unique_id_configured()

                data = {CONF_HOST: host, CONF_TOKEN: token, CONF_NAME: name}
                if model is not None:
                    data[CONF_MODEL] = model

                return self.async_create_entry(title=name, data=data)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import an existing `fan: - platform: xiaomi_miio_fan` entry from YAML."""
        host = import_config[CONF_HOST]

        await self.async_set_unique_id(f"{DOMAIN}-{host}")
        self._abort_if_unique_id_configured()

        # Only keep the keys this integration understands. The validated YAML
        # dict can also carry platform-schema extras (e.g. `platform`, a
        # `scan_interval` timedelta) that aren't JSON-serializable and have no
        # place in a config entry.
        name = import_config.get(CONF_NAME, DEFAULT_NAME)
        data = {
            CONF_HOST: host,
            CONF_TOKEN: import_config[CONF_TOKEN],
            CONF_NAME: name,
        }
        if import_config.get(CONF_MODEL) is not None:
            data[CONF_MODEL] = import_config[CONF_MODEL]

        options = {}
        if import_config.get(CONF_RETRIES) is not None:
            options[CONF_RETRIES] = import_config[CONF_RETRIES]
        if import_config.get(CONF_PRESET_MODES_OVERRIDE) is not None:
            options[CONF_PRESET_MODES_OVERRIDE] = import_config[
                CONF_PRESET_MODES_OVERRIDE
            ]

        _LOGGER.info(
            "Importing Xiaomi Mi Smart Pedestal Fan %s from configuration.yaml", host
        )
        return self.async_create_entry(title=name, data=data, options=options)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manually fix the host/token, e.g. after an IP change auto-heal couldn't reach.

        The integration tries to re-locate a fan on its own when its IP
        changes (see `discovery.py`), but that only works within the same
        broadcast domain/subnet. This is the manual fallback for everything
        else (a different VLAN, a changed token, a replaced router).
        """
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None

        if user_input is not None:
            host = user_input[CONF_HOST]
            token = user_input[CONF_TOKEN]
            try:
                await _async_get_device_info(self.hass, host, token)
            except DeviceException:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, CONF_HOST: host, CONF_TOKEN: token},
                    reason="reconfigure_successful",
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=entry.data.get(CONF_HOST, "")): str,
                    vol.Required(
                        CONF_TOKEN, default=entry.data.get(CONF_TOKEN, "")
                    ): vol.All(str, vol.Length(min=32, max=32)),
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> XiaomiMiioFanOptionsFlow:
        """Get the options flow for this handler."""
        return XiaomiMiioFanOptionsFlow(config_entry)


class XiaomiMiioFanOptionsFlow(config_entries.OptionsFlow):
    """Handle options (retries, preset mode override) for a configured fan."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            raw_override = user_input.get(CONF_PRESET_MODES_OVERRIDE, "").strip()
            preset_modes_override = (
                [mode.strip() for mode in raw_override.split(",") if mode.strip()]
                if raw_override
                else None
            )
            return self.async_create_entry(
                data={
                    CONF_RETRIES: user_input[CONF_RETRIES],
                    CONF_PRESET_MODES_OVERRIDE: preset_modes_override,
                }
            )

        current = {**self._config_entry.data, **self._config_entry.options}
        current_override = current.get(CONF_PRESET_MODES_OVERRIDE) or []

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_RETRIES,
                        default=current.get(CONF_RETRIES, DEFAULT_RETRIES),
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_PRESET_MODES_OVERRIDE,
                        default=", ".join(current_override),
                    ): str,
                }
            ),
        )
