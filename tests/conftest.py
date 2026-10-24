"""Fixtures for Zoraxy tests."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/ in every test."""
    yield


@pytest.fixture(autouse=True)
def stub_frontend():
    """The real frontend needs the hass_frontend package, which tests don't install."""
    with (
        patch("homeassistant.components.frontend.async_setup", return_value=True),
        patch("custom_components.zoraxy.add_extra_js_url") as add_js,
    ):
        yield add_js
