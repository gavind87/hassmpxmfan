"""Tests for the config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.data_entry_flow import FlowResultType
from miio import DeviceException
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.xiaomi_miio_fan.const import CONF_RETRIES, DOMAIN

HOST = "192.168.1.50"
TOKEN = "0123456789abcdef0123456789abcdef"

PROBE = "custom_components.xiaomi_miio_fan.config_flow._async_get_device_info"
SETUP = "custom_components.xiaomi_miio_fan.async_setup_entry"


async def _start_user_flow(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_user_flow_creates_entry(hass):
    """A reachable fan produces a config entry."""
    result = await _start_user_flow(hass)
    assert result["type"] == FlowResultType.FORM

    with patch(PROBE), patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_TOKEN: TOKEN, CONF_NAME: "Bedroom"},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bedroom"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_TOKEN] == TOKEN


async def test_user_flow_cannot_connect(hass):
    """An unreachable fan re-shows the form with an error."""
    result = await _start_user_flow(hass)

    with patch(PROBE, side_effect=DeviceException("nope")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_TOKEN: TOKEN}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_rejects_duplicate_host(hass):
    """Adding the same host twice aborts."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{DOMAIN}-{HOST}",
        data={CONF_HOST: HOST, CONF_TOKEN: TOKEN},
    ).add_to_hass(hass)

    result = await _start_user_flow(hass)
    with patch(PROBE):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_TOKEN: TOKEN}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow_splits_data_and_options(hass):
    """YAML import keeps connection details as data, tuning as options."""
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: HOST,
                CONF_TOKEN: TOKEN,
                CONF_NAME: "Imported",
                CONF_RETRIES: 5,
                "platform": DOMAIN,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: HOST, CONF_TOKEN: TOKEN, CONF_NAME: "Imported"}
    assert result["options"] == {CONF_RETRIES: 5}
