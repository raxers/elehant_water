"""Tests for the Elehant sensors."""

from typing import Any

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
    UnitOfEnergy,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.elehant_water.const import DOMAIN

from . import (
    ELECTRICITY_ADDRESS,
    GAS_ADDRESS,
    GAS_SERVICE_INFO,
    SVD15_ADDRESS,
    SVT15_V5_ADDRESS,
    SVT15_V5_PAYLOAD,
    WATER_ADDRESS,
    WATER_PAYLOAD,
    WATER_SERVICE_INFO,
    electricity_payload,
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

    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{GAS_ADDRESS}-temperature"
        )
        is None
    )


async def test_two_tariff_meter(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a two-tariff water meter reporting both tariffs in one packet."""
    await _setup_entry(hass, SVT15_V5_ADDRESS)
    async_get_advertisement_callback(hass)(
        make_service_info(SVT15_V5_ADDRESS, SVT15_V5_PAYLOAD)
    )
    await hass.async_block_till_done()

    for tariff, value in ((1, "19088.743"), (2, "11259.375")):
        state = hass.states.get(
            _entity_id(entity_registry, SVT15_V5_ADDRESS, f"volume_tariff_{tariff}")
        )
        assert state is not None
        assert state.state == value
        assert state.name == f"СВТ-15 4660 Tariff {tariff}"
        assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.WATER


async def test_electricity_meter(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that rotating electricity packets add up to a full set of sensors."""
    await _setup_entry(hass, ELECTRICITY_ADDRESS)
    callback = async_get_advertisement_callback(hass)
    callback(
        make_service_info(
            ELECTRICITY_ADDRESS,
            electricity_payload(0, bytes.fromhex("15cd5b07e8030000")),
        )
    )
    await hass.async_block_till_done()
    callback(
        make_service_info(
            ELECTRICITY_ADDRESS,
            electricity_payload(33, bytes.fromhex("fc08f208e6080000")),
        )
    )
    await hass.async_block_till_done()

    energy = hass.states.get(
        _entity_id(entity_registry, ELECTRICITY_ADDRESS, "energy_import")
    )
    assert energy is not None
    assert energy.state == "123456.789"
    assert energy.name == "МИР С-01 42 Active energy import"
    assert energy.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENERGY
    assert energy.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfEnergy.KILO_WATT_HOUR

    voltage = hass.states.get(
        _entity_id(entity_registry, ELECTRICITY_ADDRESS, "voltage_b")
    )
    assert voltage is not None
    assert voltage.state == "229.0"
    assert voltage.name == "МИР С-01 42 Phase B voltage"

    # Electricity meters have no battery.
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{ELECTRICITY_ADDRESS}-battery"
        )
        is None
    )


async def test_other_meter_ignored(hass: HomeAssistant) -> None:
    """Test that advertisements of other meters do not create entities."""
    await _setup_entry(hass, WATER_ADDRESS)
    async_get_advertisement_callback(hass)(GAS_SERVICE_INFO)
    await hass.async_block_till_done()
    assert not hass.states.async_all("sensor")


def _restore_storage(
    hass_storage: dict[str, Any], entry_id: str, sw_version: str, device_class: str
) -> None:
    """Store processor data as saved by version 1.0.1 of the integration."""
    hass_storage["bluetooth.passive_update_processor"] = {
        "version": 1,
        "minor_version": 1,
        "key": "bluetooth.passive_update_processor",
        "data": {
            entry_id: {
                "sensor": {
                    "devices": {"": {"name": "meter", "sw_version": sw_version}},
                    "entity_descriptions": {
                        "volume___": {
                            "key": "volume",
                            "device_class": device_class,
                            "native_unit_of_measurement": "m³",
                        },
                        "temperature___": {
                            "key": "temperature",
                            "device_class": "temperature",
                            "native_unit_of_measurement": "°C",
                        },
                    },
                    "entity_names": {},
                    "entity_data": {"volume___": 1.5, "temperature___": 40.5},
                }
            }
        },
    }


@pytest.mark.parametrize(
    ("address", "sw_version", "device_class", "has_temperature"),
    [
        (GAS_ADDRESS, "1.5", "gas", False),
        (SVD15_ADDRESS, "3.3", "water", True),
        # СВД-15 firmware without a temperature sensor.
        (SVD15_ADDRESS, "1.7", "water", False),
    ],
)
async def test_invalid_temperature_removed(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    entity_registry: er.EntityRegistry,
    address: str,
    sw_version: str,
    device_class: str,
    has_temperature: bool,
) -> None:
    """Test that restored temperature sensors of meters without one are removed."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=address)
    _restore_storage(hass_storage, entry.entry_id, sw_version, device_class)
    entry.add_to_hass(hass)
    for key in ("volume", "temperature"):
        entity_registry.async_get_or_create(
            "sensor", DOMAIN, f"{address}-{key}", config_entry=entry
        )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Restored sensors exist, unavailable until the meter is heard again.
    assert hass.states.get(_entity_id(entity_registry, address, "volume")) is not None
    temperature_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{address}-temperature"
    )
    assert (temperature_id is not None) is has_temperature
    if has_temperature:
        assert hass.states.get(temperature_id) is not None
    else:
        assert not [
            state
            for state in hass.states.async_all("sensor")
            if "temperature" in state.entity_id
        ]
