"""Sensor platform for Elehant meters."""

from __future__ import annotations

from dataclasses import replace

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactiveEnergy,
    UnitOfReactivePower,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ElehantConfigEntry, parser as p
from .const import DOMAIN, MANUFACTURER

SIGNAL_STRENGTH = "signal_strength"

_TEMPERATURE = SensorEntityDescription(
    key=p.TEMPERATURE,
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
)
_ENERGY = SensorEntityDescription(
    key=p.ENERGY_IMPORT,
    device_class=SensorDeviceClass.ENERGY,
    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    state_class=SensorStateClass.TOTAL_INCREASING,
    suggested_display_precision=3,
)
_REACTIVE_ENERGY = SensorEntityDescription(
    key=p.REACTIVE_ENERGY_IMPORT,
    device_class=SensorDeviceClass.REACTIVE_ENERGY,
    native_unit_of_measurement=UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
    state_class=SensorStateClass.TOTAL_INCREASING,
    suggested_display_precision=3,
)
_VOLTAGE = SensorEntityDescription(
    key=p.VOLTAGE,
    device_class=SensorDeviceClass.VOLTAGE,
    native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=1,
)
_CURRENT = SensorEntityDescription(
    key=p.CURRENT,
    device_class=SensorDeviceClass.CURRENT,
    native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=2,
)


def _descriptions() -> dict[str, SensorEntityDescription]:
    """Build descriptions of all values except the meter-type dependent volume."""
    descriptions = [
        SensorEntityDescription(
            key=p.ENERGY,
            device_class=SensorDeviceClass.ENERGY,
            native_unit_of_measurement=UnitOfEnergy.GIGA_JOULE,
            state_class=SensorStateClass.TOTAL_INCREASING,
            suggested_display_precision=3,
        ),
        SensorEntityDescription(
            key=p.COOLANT_VOLUME,
            translation_key=p.COOLANT_VOLUME,
            device_class=SensorDeviceClass.VOLUME,
            native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
            state_class=SensorStateClass.TOTAL_INCREASING,
            suggested_display_precision=4,
        ),
        _TEMPERATURE,
        replace(
            _TEMPERATURE, key=p.TEMPERATURE_INLET, translation_key=p.TEMPERATURE_INLET
        ),
        replace(
            _TEMPERATURE,
            key=p.TEMPERATURE_OUTLET,
            translation_key=p.TEMPERATURE_OUTLET,
        ),
        SensorEntityDescription(
            key=p.BATTERY,
            device_class=SensorDeviceClass.BATTERY,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        SensorEntityDescription(
            key=SIGNAL_STRENGTH,
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        ),
        _VOLTAGE,
        _CURRENT,
        replace(_CURRENT, key=p.NEUTRAL_CURRENT, translation_key=p.NEUTRAL_CURRENT),
        replace(
            _CURRENT,
            key=p.DIFFERENTIAL_CURRENT,
            translation_key=p.DIFFERENTIAL_CURRENT,
        ),
        SensorEntityDescription(
            key=p.APPARENT_POWER,
            device_class=SensorDeviceClass.APPARENT_POWER,
            native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
        ),
        SensorEntityDescription(
            key=p.ACTIVE_POWER,
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
        ),
        SensorEntityDescription(
            key=p.REACTIVE_POWER,
            device_class=SensorDeviceClass.REACTIVE_POWER,
            native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
        ),
        SensorEntityDescription(
            key=p.FREQUENCY,
            device_class=SensorDeviceClass.FREQUENCY,
            native_unit_of_measurement=UnitOfFrequency.HERTZ,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=2,
        ),
        SensorEntityDescription(
            key=p.POWER_FACTOR,
            device_class=SensorDeviceClass.POWER_FACTOR,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=2,
        ),
    ]
    for base, key in (
        (_ENERGY, p.ENERGY_IMPORT),
        (_ENERGY, p.ENERGY_EXPORT),
        (_REACTIVE_ENERGY, p.REACTIVE_ENERGY_IMPORT),
        (_REACTIVE_ENERGY, p.REACTIVE_ENERGY_EXPORT),
    ):
        descriptions.append(replace(base, key=key, translation_key=key))
        descriptions.extend(
            replace(
                base,
                key=p.tariff_key(key, tariff),
                translation_key=f"{key}_tariff",
                translation_placeholders={"tariff": str(tariff)},
            )
            for tariff in range(1, 5)
        )
    for phase in ("a", "b", "c"):
        descriptions.append(
            replace(
                _VOLTAGE,
                key=p.phase_key(p.VOLTAGE, phase),
                translation_key="voltage_phase",
                translation_placeholders={"phase": phase.upper()},
            )
        )
        descriptions.append(
            replace(
                _CURRENT,
                key=p.phase_key(p.CURRENT, phase),
                translation_key="current_phase",
                translation_placeholders={"phase": phase.upper()},
            )
        )
    descriptions.extend(
        replace(
            _VOLTAGE,
            key=p.phase_key(p.VOLTAGE, phases),
            translation_key="voltage_line",
            translation_placeholders={"phases": phases.upper()},
        )
        for phases in ("ab", "bc", "ca")
    )
    return {description.key: description for description in descriptions}


DESCRIPTIONS = _descriptions()

_VOLUME_DEVICE_CLASSES = {
    p.MeterType.GAS: SensorDeviceClass.GAS,
    p.MeterType.WATER: SensorDeviceClass.WATER,
}


def _description(meter_type: p.MeterType, key: str) -> SensorEntityDescription:
    """Return the description of a decoded value."""
    if description := DESCRIPTIONS.get(key):
        return description
    # Gas or water volume, possibly per tariff.
    description = SensorEntityDescription(
        key=key,
        device_class=_VOLUME_DEVICE_CLASSES[meter_type],
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=4,
    )
    if key != p.VOLUME:
        tariff = key.rsplit("_", 1)[1]
        description = replace(
            description,
            translation_key="volume_tariff",
            translation_placeholders={"tariff": tariff},
        )
    return description


def service_info_to_bluetooth_data_update(
    service_info: BluetoothServiceInfoBleak,
) -> PassiveBluetoothDataUpdate[float]:
    """Decode an advertisement into entity updates."""
    reading = p.parse_manufacturer_data(
        service_info.address, service_info.manufacturer_data
    )
    if reading is None:
        return PassiveBluetoothDataUpdate(
            devices={}, entity_descriptions={}, entity_names={}, entity_data={}
        )

    values = {**reading.values, SIGNAL_STRENGTH: service_info.rssi}
    return PassiveBluetoothDataUpdate(
        devices={
            None: DeviceInfo(
                name=reading.title,
                manufacturer=MANUFACTURER,
                model=reading.model,
                serial_number=str(reading.serial),
                sw_version=reading.firmware,
            )
        },
        entity_descriptions={
            PassiveBluetoothEntityKey(key, None): _description(reading.meter_type, key)
            for key in values
        },
        entity_names={},
        entity_data={
            PassiveBluetoothEntityKey(key, None): value for key, value in values.items()
        },
    )


@callback
def _async_remove_invalid_temperature(
    hass: HomeAssistant, entry: ElehantConfigEntry
) -> None:
    """Remove the temperature sensor of meters that do not measure it.

    Up to version 1.0.1 every meter got a temperature sensor, including gas
    meters where the field holds garbage. The restored processor data would
    recreate it on every start, so drop it from there and from the registry.
    """
    coordinator = entry.runtime_data
    if (meter := p.parse_address(coordinator.address)) is None or (
        info := p.MODELS[meter[0]].get(meter[1])
    ) is None:
        return
    restored = coordinator.restore_data.get(SENSOR_DOMAIN)
    firmware = 0
    if restored and (device := restored["devices"].get("")):
        if sw_version := device.get("sw_version"):
            firmware = round(float(sw_version) * 10)
    if info.has_temperature(firmware):
        return

    if restored:
        key = PassiveBluetoothEntityKey(p.TEMPERATURE, None).to_string()
        for section in ("entity_descriptions", "entity_names", "entity_data"):
            restored[section].pop(key, None)  # type: ignore[literal-required]
    registry = er.async_get(hass)
    if entity_id := registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{coordinator.address}-{p.TEMPERATURE}"
    ):
        registry.async_remove(entity_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElehantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elehant sensors."""
    coordinator = entry.runtime_data
    _async_remove_invalid_temperature(hass, entry)
    processor = PassiveBluetoothDataProcessor(service_info_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(ElehantSensorEntity, async_add_entities)
    )
    entry.async_on_unload(
        coordinator.async_register_processor(processor, SensorEntityDescription)
    )


class ElehantSensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[float, BluetoothServiceInfoBleak]
    ],
    SensorEntity,
):
    """Representation of an Elehant meter sensor."""

    @property
    def native_value(self) -> float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
