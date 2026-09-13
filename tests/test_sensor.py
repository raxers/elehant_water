"""Tests for the Elehant sensors."""

from homeassistant.components.bluetooth import async_get_advertisement_callback
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.elehant_water.const import DOMAIN

from . import (
    GAS_ADDRESS,
    GAS_SERVICE_INFO,
    WATER_ADDRESS,
    WATER_PAYLOAD,
    WATER_SERVICE_INFO,
    make_service_info,
)


def _device(
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    entity_id: str,
) -> dr.DeviceEntry:
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id is not None
    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    return device


async def _setup_entry(hass: HomeAssistant, address: str) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=address)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _entity_id(entity_registry: er.EntityRegistry, address: str, key: str) -> str:
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{address}-{key}"
    )
    assert entity_id is not None
    return entity_id


async def test_water_meter(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test sensors of a water meter."""
    entry = await _setup_entry(hass, WATER_ADDRESS)
    assert not hass.states.async_all("sensor")

    async_get_advertisement_callback(hass)(WATER_SERVICE_INFO)
    await hass.async_block_till_done()

    volume = hass.states.get(_entity_id(entity_registry, WATER_ADDRESS, "volume"))
    assert volume is not None
    assert volume.state == "0.0057"
    assert volume.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.WATER
    assert volume.attributes[ATTR_STATE_CLASS] == SensorStateClass.TOTAL_INCREASING
    assert volume.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfVolume.CUBIC_METERS

    temperature = hass.states.get(
        _entity_id(entity_registry, WATER_ADDRESS, "temperature")
    )
    assert temperature is not None
    assert temperature.state == "27.12"
    assert temperature.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS

    battery = hass.states.get(_entity_id(entity_registry, WATER_ADDRESS, "battery"))
    assert battery is not None
    assert battery.state == "100"
    assert battery.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE

    signal = entity_registry.async_get(
        _entity_id(entity_registry, WATER_ADDRESS, "signal_strength")
    )
    assert signal is not None
    assert signal.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    device = _device(entity_registry, device_registry, volume.entity_id)
    assert (dr.CONNECTION_BLUETOOTH, WATER_ADDRESS) in device.connections
    assert device.name == "СВД-15 9960"
    assert device.manufacturer == "Elehant"
    assert device.model == "СВД-15"
    assert device.serial_number == "9960"
    assert device.sw_version is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_reading_updates(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that a new advertisement updates the reading."""
    await _setup_entry(hass, WATER_ADDRESS)
    async_get_advertisement_callback(hass)(WATER_SERVICE_INFO)
    await hass.async_block_till_done()

    payload = bytearray(WATER_PAYLOAD)
    payload[1] += 1
    payload[9:13] = (123456).to_bytes(4, "little")
    async_get_advertisement_callback(hass)(
        make_service_info(WATER_ADDRESS, bytes(payload))
    )
    await hass.async_block_till_done()

    volume = hass.states.get(_entity_id(entity_registry, WATER_ADDRESS, "volume"))
    assert volume is not None
    assert volume.state == "12.3456"


async def test_gas_meter(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test sensors of a gas meter."""
    await _setup_entry(hass, GAS_ADDRESS)
    async_get_advertisement_callback(hass)(GAS_SERVICE_INFO)
    await hass.async_block_till_done()

    volume = hass.states.get(_entity_id(entity_registry, GAS_ADDRESS, "volume"))
    assert volume is not None
    assert volume.state == "0.2553"
    assert volume.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.GAS

    device = _device(entity_registry, device_registry, volume.entity_id)
    assert device.model == "СГБД-4.0"
    assert device.sw_version == "1.5"


async def test_other_meter_ignored(hass: HomeAssistant) -> None:
    """Test that advertisements of other meters do not create entities."""
    await _setup_entry(hass, WATER_ADDRESS)
    async_get_advertisement_callback(hass)(GAS_SERVICE_INFO)
    await hass.async_block_till_done()
    assert not hass.states.async_all("sensor")
