"""Sensor platform for Elehant meters."""

from __future__ import annotations

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ElehantConfigEntry
from .const import MANUFACTURER
from .parser import MeterType, parse_manufacturer_data

VOLUME_DESCRIPTIONS: dict[MeterType, SensorEntityDescription] = {
    MeterType.WATER: SensorEntityDescription(
        key="volume",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
    ),
    MeterType.GAS: SensorEntityDescription(
        key="volume",
        device_class=SensorDeviceClass.GAS,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
    ),
}

TEMPERATURE_DESCRIPTION = SensorEntityDescription(
    key="temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
)

BATTERY_DESCRIPTION = SensorEntityDescription(
    key="battery",
    device_class=SensorDeviceClass.BATTERY,
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
)

SIGNAL_STRENGTH_DESCRIPTION = SensorEntityDescription(
    key="signal_strength",
    device_class=SensorDeviceClass.SIGNAL_STRENGTH,
    native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
)


def service_info_to_bluetooth_data_update(
    service_info: BluetoothServiceInfoBleak,
) -> PassiveBluetoothDataUpdate[float | int]:
    """Decode an advertisement into entity updates."""
    reading = parse_manufacturer_data(
        service_info.address, service_info.manufacturer_data
    )
    if reading is None:
        return PassiveBluetoothDataUpdate(
            devices={}, entity_descriptions={}, entity_names={}, entity_data={}
        )

    values: list[tuple[SensorEntityDescription, float | int]] = [
        (VOLUME_DESCRIPTIONS[reading.meter_type], reading.volume),
        (TEMPERATURE_DESCRIPTION, reading.temperature),
        (BATTERY_DESCRIPTION, reading.battery),
        (SIGNAL_STRENGTH_DESCRIPTION, service_info.rssi),
    ]
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
            PassiveBluetoothEntityKey(description.key, None): description
            for description, _ in values
        },
        entity_names={},
        entity_data={
            PassiveBluetoothEntityKey(description.key, None): value
            for description, value in values
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElehantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elehant sensors."""
    coordinator = entry.runtime_data
    processor = PassiveBluetoothDataProcessor(service_info_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(ElehantSensorEntity, async_add_entities)
    )
    entry.async_on_unload(
        coordinator.async_register_processor(processor, SensorEntityDescription)
    )


class ElehantSensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[float | int, BluetoothServiceInfoBleak]
    ],
    SensorEntity,
):
    """Representation of an Elehant meter sensor."""

    @property
    def native_value(self) -> float | int | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
