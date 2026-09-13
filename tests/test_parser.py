"""Tests for the Elehant advertisement decoder."""

import pytest

from custom_components.elehant_water.parser import (
    ElehantReading,
    MeterType,
    parse_advertisement,
    parse_meter,
)

from . import (
    ELECTRICITY_ADDRESS,
    GAS_ADDRESS,
    GAS_PAYLOAD,
    GAS_REAL_ADDRESS,
    GAS_REAL_PAYLOAD,
    SVD15_ADDRESS,
    SVD15_PAYLOAD,
    SVD20_ADDRESS,
    SVD20_PAYLOAD,
    SVT15_V5_ADDRESS,
    SVT15_V5_PAYLOAD,
    WATER_ADDRESS,
    WATER_B1_PAYLOAD,
    WATER_PAYLOAD,
    electricity_payload,
)


def _values(address: str, payload: bytes) -> dict[str, float]:
    reading = parse_advertisement(address, payload)
    assert reading is not None
    return dict(reading.values)


def test_parse_water_meter() -> None:
    """Test decoding a real СВД-15 advertisement."""
    assert parse_advertisement(WATER_ADDRESS, WATER_PAYLOAD) == ElehantReading(
        meter_type=MeterType.WATER,
        model_id=1,
        serial=9960,
        packet_version=1,
        firmware=None,
        values={"volume": 0.0057, "battery": 100, "temperature": 27.12},
    )


def test_parse_real_meters() -> None:
    """Test packets from real meters against the official app's readings."""
    reading = parse_advertisement(SVD15_ADDRESS, SVD15_PAYLOAD)
    assert reading is not None
    assert reading.title == "СВД-15 12345"
    assert reading.firmware == "3.3"
    assert reading.values == {"volume": 158.949, "battery": 63, "temperature": 21.92}

    reading = parse_advertisement(SVD20_ADDRESS, SVD20_PAYLOAD)
    assert reading is not None
    assert reading.firmware == "2.2"
    # Battery byte 127 is shown as 100% by the app.
    assert reading.values == {"volume": 67.9492, "battery": 100, "temperature": 19.24}


def test_gas_meter_has_no_temperature() -> None:
    """Test that gas meters do not report the meaningless temperature field."""
    reading = parse_advertisement(GAS_REAL_ADDRESS, GAS_REAL_PAYLOAD)
    assert reading is not None
    assert reading.title == "СГБД-4.0 1365"
    assert reading.firmware == "1.1"
    assert reading.values == {"volume": 353.5777, "battery": 100}


def test_temperature_hidden_for_firmware() -> None:
    """Test firmware versions of СВД-15 without a temperature sensor."""
    payload = bytearray(SVD15_PAYLOAD)
    payload[16] = 17
    assert "temperature" not in _values(SVD15_ADDRESS, bytes(payload))


def test_negative_temperature() -> None:
    """Test that the temperature is signed."""
    payload = bytearray(SVD15_PAYLOAD)
    payload[14:16] = (-512).to_bytes(2, "little", signed=True)
    assert _values(SVD15_ADDRESS, bytes(payload))["temperature"] == -5.12


@pytest.mark.parametrize(
    ("raw", "battery"),
    [(0, 1), (1, 1), (63, 63), (100, 100), (101, 100), (171, 100), (172, 1)],
)
def test_battery(raw: int, battery: int) -> None:
    """Test the battery conversion of the official app."""
    payload = bytearray(SVD15_PAYLOAD)
    payload[13] = raw
    assert _values(SVD15_ADDRESS, bytes(payload))["battery"] == battery


def test_high_resolution_counter() -> None:
    """Test the extra counter digit of high resolution packets."""
    payload = bytearray(SVD15_PAYLOAD)
    payload[0] |= 0x04
    payload[2] = 0xA7
    assert _values(SVD15_ADDRESS, bytes(payload))["volume"] == pytest.approx(158.94907)


def test_heat_meter() -> None:
    """Test that heat meters report energy instead of volume."""
    payload = bytearray(SVD15_PAYLOAD)
    payload[4:6] = b"\x04\x01"
    values = _values("B0:01:04:00:30:39", bytes(payload))
    assert values == {"energy": 158.949, "battery": 63, "temperature": 21.92}


def test_two_tariff_v5() -> None:
    """Test a packet carrying both tariffs of a two-tariff water meter."""
    reading = parse_advertisement(SVT15_V5_ADDRESS, SVT15_V5_PAYLOAD)
    assert reading is not None
    assert reading.title == "СВТ-15 4660"
    assert reading.firmware == "3.0"
    assert reading.values == {
        "volume_tariff_1": 19088.743,
        "volume_tariff_2": 11259.375,
        "battery": 87,
        "temperature": 24,
    }


def test_two_tariff_v5_from_second_tariff_address() -> None:
    """Test that the first counter belongs to the advertising tariff model."""
    payload = bytearray(SVT15_V5_PAYLOAD)
    payload[5] = 3
    values = _values("B0:03:02:00:12:34", bytes(payload))
    assert values["volume_tariff_2"] == 19088.743
    assert values["volume_tariff_1"] == 11259.375


def test_two_tariff_v1_title() -> None:
    """Test that each tariff address of a V1 two-tariff meter is named."""
    payload = bytearray(SVD15_PAYLOAD)
    payload[5] = 3
    reading = parse_advertisement("B0:03:02:00:30:39", bytes(payload))
    assert reading is not None
    assert reading.title == "СВТ-15 12345, тариф 2"
    assert reading.values["volume"] == 158.949


def test_coolant_packet_v9() -> None:
    """Test the coolant volume and temperatures packet."""
    payload = bytes.fromhex("8000000904013930001027000034082c01")
    values = _values("B0:01:04:00:30:39", payload)
    assert values == {
        "coolant_volume": 1.0,
        "temperature_inlet": 21.0,
        "temperature_outlet": 3.0,
    }


@pytest.mark.parametrize(
    ("version", "data", "expected"),
    [
        (
            0,
            bytes.fromhex("15cd5b07e8030000"),
            {"energy_import": 123456.789, "energy_export": 1.0},
        ),
        (
            2,
            bytes.fromhex("15cd5b07e8030000"),
            {"energy_import_tariff_2": 123456.789, "energy_export_tariff_2": 1.0},
        ),
        (
            16,
            bytes.fromhex("e8030000d0070000"),
            {"reactive_energy_import": 1.0, "reactive_energy_export": 2.0},
        ),
        (
            20,
            bytes.fromhex("e8030000d0070000"),
            {
                "reactive_energy_import_tariff_4": 1.0,
                "reactive_energy_export_tariff_4": 2.0,
            },
        ),
        (
            32,
            bytes.fromhex("fc08e8030a000100"),
            {
                "voltage": 230.0,
                "current": 10.0,
                "neutral_current": 0.1,
                "differential_current": 0.01,
            },
        ),
        (
            33,
            bytes.fromhex("fc08f208e6080000"),
            {"voltage_a": 230.0, "voltage_b": 229.0, "voltage_c": 227.8},
        ),
        (
            34,
            bytes.fromhex("f40ffc0f04100000"),
            {"voltage_ab": 408.4, "voltage_bc": 409.2, "voltage_ca": 410.0},
        ),
        (
            35,
            bytes.fromhex("6400c8002c010a00"),
            {
                "current_a": 1.0,
                "current_b": 2.0,
                "current_c": 3.0,
                "neutral_current": 0.1,
            },
        ),
        (
            48,
            bytes.fromhex("a0860100881362ff"),
            {"apparent_power": 1000.0, "frequency": 50.0, "power_factor": 0.98},
        ),
        (
            49,
            bytes.fromhex("400d030050c30000"),
            {"active_power": 2000.0, "reactive_power": 500.0},
        ),
    ],
)
def test_electricity(version: int, data: bytes, expected: dict[str, float]) -> None:
    """Test the rotating electricity meter packets."""
    reading = parse_advertisement(
        ELECTRICITY_ADDRESS, electricity_payload(version, data)
    )
    assert reading is not None
    assert reading.model == "МИР С-01"
    assert reading.values == pytest.approx(expected)


def test_identify_meter_from_history_packet() -> None:
    """Test that a meter is identified from packets without readings."""
    payload = _with(SVD15_PAYLOAD, b3=8)
    assert parse_advertisement(SVD15_ADDRESS, payload) is None
    meter = parse_meter(SVD15_ADDRESS, payload)
    assert meter is not None
    assert meter.title == "СВД-15 12345"
    assert meter.values == {}


def test_c0_address_prefix() -> None:
    """Test that the C0 address prefix is accepted like B0."""
    assert parse_advertisement("C0:01:02:00:30:39", SVD15_PAYLOAD) is not None


def test_parse_without_mac_address() -> None:
    """Test that platforms exposing UUIDs instead of MACs are supported."""
    reading = parse_advertisement("7A1C5E4B-0000-4000-8000-00000000ABCD", WATER_PAYLOAD)
    assert reading is not None
    assert reading.serial == 9960


def _with(payload: bytes, **changes: int) -> bytes:
    data = bytearray(payload)
    for offset, value in changes.items():
        data[int(offset[1:])] = value
    return bytes(data)


@pytest.mark.parametrize(
    ("address", "payload"),
    [
        # Encrypted packet sent from the B1 address.
        ("B1:01:02:00:26:E8", WATER_B1_PAYLOAD),
        # Serial in the address does not match the payload.
        ("B0:01:02:00:26:E1", WATER_PAYLOAD),
        # Meter type in the address does not match the payload.
        ("B0:01:01:00:26:E8", WATER_PAYLOAD),
        # Truncated payload.
        (WATER_ADDRESS, WATER_PAYLOAD[:16]),
        # Packet not marked valid.
        (WATER_ADDRESS, _with(WATER_PAYLOAD, b0=0x7F)),
        # Consumption history packet.
        (SVD15_ADDRESS, _with(SVD15_PAYLOAD, b3=8)),
        # Unknown packet version.
        (SVD15_ADDRESS, _with(SVD15_PAYLOAD, b3=2)),
        # Unknown model.
        ("B0:42:02:00:30:39", _with(SVD15_PAYLOAD, b5=0x42)),
        # Unsupported meter type (WiFi box).
        ("B0:02:07:00:30:39", _with(SVD15_PAYLOAD, b4=7, b5=2)),
        # Zero serial.
        ("B0:01:02:00:00:00", _with(SVD15_PAYLOAD, b6=0, b7=0, b8=0)),
        # Unknown electricity packet.
        (ELECTRICITY_ADDRESS, electricity_payload(64, bytes(8))),
        # Gas meters do not send two-tariff packets.
        (GAS_ADDRESS, _with(GAS_PAYLOAD, b3=5)),
    ],
)
def test_rejected(address: str, payload: bytes) -> None:
    """Test that foreign, inconsistent or unsupported packets are ignored."""
    assert parse_advertisement(address, payload) is None
