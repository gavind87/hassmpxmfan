"""Shared fixtures for the Xiaomi Mi Smart Pedestal Fan tests."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load integrations from `custom_components/`."""
    return
