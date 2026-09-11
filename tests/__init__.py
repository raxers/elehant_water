"""Tests for the Elehant integration."""

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from homeassistant.components.bluetooth import (
    MONOTONIC_TIME,
    SOURCE_LOCAL,
    BluetoothServiceInfoBleak,
)

from custom_components.elehant_water.parser import MANUFACTURER_ID

# Real СВД-15 advertisements captured by vooon/elehant-to-mqtt
# (dumps/advertisments-svd-15-9953-9960.log), company id stripped.
WATER_ADDRESS = "B0:01:02:00:26:E8"
WATER_PAYLOAD = bytes.fromhex("80E70A010201E826003900000065980A00")
WATER_B1_ADDRESS = "B1:01:02:00:26:E8"
WATER_B1_PAYLOAD = bytes.fromhex("80246C72A598DEA4CFF3D7F0DAD3BF253A")

# СГБД-4.0 advertisement from the same project's protocol notes,
# with the serial 0x010203 filled in.
GAS_ADDRESS = "B0:12:01:01:02:03"
GAS_PAYLOAD = bytes.fromhex("80A896010112030201F90900007F710B0F")


def make_service_info(
    address: str, payload: bytes, rssi: int = -60
) -> BluetoothServiceInfoBleak:
    """Build service info for an advertisement carrying Elehant data."""
    manufacturer_data = {MANUFACTURER_ID: payload}
    return BluetoothServiceInfoBleak(
        name=address,
        address=address,
        rssi=rssi,
        manufacturer_data=manufacturer_data,
        service_data={},
        service_uuids=[],
        source=SOURCE_LOCAL,
        device=BLEDevice(address=address, name=None, details={}),
        advertisement=AdvertisementData(
            local_name=None,
            manufacturer_data=manufacturer_data,
            service_data={},
            service_uuids=[],
            tx_power=-127,
            rssi=rssi,
            platform_data=((),),
        ),
        connectable=False,
        time=MONOTONIC_TIME(),
        tx_power=-127,
        raw=None,
    )


WATER_SERVICE_INFO = make_service_info(WATER_ADDRESS, WATER_PAYLOAD)
WATER_B1_SERVICE_INFO = make_service_info(WATER_B1_ADDRESS, WATER_B1_PAYLOAD)
GAS_SERVICE_INFO = make_service_info(GAS_ADDRESS, GAS_PAYLOAD)
