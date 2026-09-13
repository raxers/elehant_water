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

# Real advertisements reported in raxers/elehant_water issues: СГБД-4.0 with
# firmware 1.1 and СВД-20 with firmware 2.2.
GAS_REAL_ADDRESS = "B0:12:01:00:05:55"
GAS_REAL_PAYLOAD = bytes.fromhex("80060a010112550500a1f335006704d90b")
SVD20_ADDRESS = "B0:02:02:00:58:69"
SVD20_PAYLOAD = bytes.fromhex("80eba0010202695800445e0a007f840716")

# Real СВД-15 advertisement with firmware 3.3 (serial replaced by 12345),
# the official app shows 63% battery for it.
SVD15_ADDRESS = "B0:01:02:00:30:39"
SVD15_PAYLOAD = bytes.fromhex("803a96010201393000f24018003f900821")

# Two-tariff СВТ-15 packet version 5 from the tariff 1 address, serial 0x1234:
# tariff 1 = 0x1234567 (19088.743 m³), tariff 2 = 0x0ABCDEF (11259.375 m³),
# battery 87%, temperature 24 °C, firmware 3.0.
SVT15_V5_ADDRESS = "B0:04:02:00:12:34"
SVT15_V5_PAYLOAD = bytes.fromhex("80571805020434120010234567abcdef1e")

# МИР С-01 electricity meter, serial 42.
ELECTRICITY_ADDRESS = "B0:01:03:00:00:2A"


def electricity_payload(version: int, data: bytes) -> bytes:
    """Build an electricity meter packet with 8 bytes of values."""
    return bytes([0x80, 0, 0, version, 3, 1, 42, 0, 0]) + data


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
