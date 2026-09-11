"""The Elehant integration."""

from __future__ import annotations

import logging

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

type ElehantConfigEntry = ConfigEntry[
    PassiveBluetoothProcessorCoordinator[BluetoothServiceInfoBleak]
]


async def async_setup_entry(hass: HomeAssistant, entry: ElehantConfigEntry) -> bool:
    """Set up an Elehant meter from a config entry."""
    assert entry.unique_id is not None
    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=entry.unique_id,
        mode=BluetoothScanningMode.PASSIVE,
        # Advertisements are decoded by the platform processor.
        update_method=lambda service_info: service_info,
    )
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Only start after all platforms have had a chance to subscribe.
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ElehantConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
