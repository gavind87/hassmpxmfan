"""Tests for the IP auto-heal logic on the fan entity."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from miio import DeviceException
import pytest

from custom_components.xiaomi_miio_fan.const import MODEL_FAN_P33
from custom_components.xiaomi_miio_fan.fan import (
    HEAL_COOLDOWN_SECONDS,
    _build_device,
)

OLD_IP = "10.0.0.5"
NEW_IP = "10.0.0.9"
DEVICE_ID = 123456


@pytest.fixture
def entity():
    """Return a fan entity wired to a fake client and discovery result."""
    client = MagicMock()
    client.ip = OLD_IP
    client._protocol = SimpleNamespace(ip=OLD_IP)

    fan = _build_device(client, MODEL_FAN_P33, "Test fan", "uid", 3, None)
    fan._device_id = DEVICE_ID
    fan.hass = MagicMock()
    fan.hass.async_add_executor_job = AsyncMock(return_value={DEVICE_ID: NEW_IP})
    return fan


async def test_heal_switches_to_new_host(entity):
    """A fan found at a new IP is re-pointed there, on both client objects."""
    assert await entity._async_try_heal_host(DeviceException("down")) is True
    assert entity._device.ip == NEW_IP
    assert entity._device._protocol.ip == NEW_IP


async def test_heal_without_device_id_does_nothing(entity):
    """Without a miIO device ID there is nothing to search for."""
    entity._device_id = None
    assert await entity._async_try_heal_host(DeviceException("down")) is False
    entity.hass.async_add_executor_job.assert_not_called()


async def test_heal_is_rate_limited(entity):
    """A second scan inside the cooldown window must not hit the network."""
    await entity._async_try_heal_host(DeviceException("down"))
    entity.hass.async_add_executor_job.reset_mock()

    assert await entity._async_try_heal_host(DeviceException("down")) is False
    entity.hass.async_add_executor_job.assert_not_called()


async def test_heal_runs_again_after_cooldown(entity):
    """Once the cooldown has passed, scanning is allowed again."""
    await entity._async_try_heal_host(DeviceException("down"))
    entity._last_heal_attempt -= HEAL_COOLDOWN_SECONDS + 1
    entity.hass.async_add_executor_job.reset_mock()

    await entity._async_try_heal_host(DeviceException("down"))
    entity.hass.async_add_executor_job.assert_called_once()


async def test_heal_ignores_same_ip(entity):
    """If the fan answers from the IP we already have, nothing changes."""
    entity.hass.async_add_executor_job.return_value = {DEVICE_ID: OLD_IP}
    assert await entity._async_try_heal_host(DeviceException("down")) is False


async def test_heal_ignores_other_devices(entity):
    """A scan that doesn't see our device ID leaves the host alone."""
    entity.hass.async_add_executor_job.return_value = {999: NEW_IP}
    assert await entity._async_try_heal_host(DeviceException("down")) is False
    assert entity._device.ip == OLD_IP


async def test_heal_degrades_if_miio_internals_change(entity):
    """If python-miio drops _protocol.ip, heal must bail out untouched."""
    entity._device._protocol = SimpleNamespace()
    assert await entity._async_try_heal_host(DeviceException("down")) is False
    assert entity._device.ip == OLD_IP
