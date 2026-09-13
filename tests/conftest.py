"""Fixtures for the Elehant integration tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

from homeassistant.helpers import discovery_flow
import pytest

from custom_components.elehant_water.const import DOMAIN


@pytest.fixture(autouse=True)
def only_own_discovery_flows() -> Generator[None]:
    """Start Bluetooth discovery flows for this integration only.

    Company id 0xFFFF is also matched by core integrations (e.g. kegtron)
    whose requirements are not installed in the test environment.
    """
    create_flow = discovery_flow.async_create_flow

    def _create_flow(hass: Any, domain: str, *args: Any, **kwargs: Any) -> None:
        if domain == DOMAIN:
            create_flow(hass, domain, *args, **kwargs)

    with patch(
        "homeassistant.components.bluetooth.manager.discovery_flow.async_create_flow",
        _create_flow,
    ):
        yield


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in all tests."""


@pytest.fixture(autouse=True)
def auto_mock_bluetooth(mock_bluetooth: None) -> None:
    """Replace the Bluetooth adapters and scanner with mocks."""
