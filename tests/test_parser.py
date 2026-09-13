"""Tests for the Elehant advertisement decoder."""

import pytest

from custom_components.elehant_water.parser import (
    ElehantReading,
    MeterType,
    parse_advertisement,
)

from . import (
    GAS_ADDRESS,
    GAS_PAYLOAD,
    WATER_ADDRESS,
    WATER_B1_PAYLOAD,
    WATER_PAYLOAD,
)


def test_parse_water_meter() -> None:
    """Test decoding a real СВД-15 advertisement."""
    assert parse_advertisement(WATER_ADDRESS, WATER_PAYLOAD) == ElehantReading(
        meter_type=MeterType.WATER,
        model_id=1,
        serial=9960,
        volume=0.0057,
        temperature=27.12,
        battery=100,
        firmware=None,
    )


def test_parse_gas_meter() -> None:
    """Test decoding a СГБД-4.0 advertisement."""
    reading = parse_advertisement(GAS_ADDRESS, GAS_PAYLOAD)
    assert reading == ElehantReading(
        meter_type=MeterType.GAS,
        model_id=18,
        serial=0x010203,
        volume=0.2553,
        temperature=29.29,
        battery=100,
        firmware="1.5",
    )
    assert reading.title == "СГБД-4.0 66051"


def test_parse_without_mac_address() -> None:
    """Test that platforms exposing UUIDs instead of MACs are supported."""
    reading = parse_advertisement("7A1C5E4B-0000-4000-8000-00000000ABCD", WATER_PAYLOAD)
    assert reading is not None
    assert reading.serial == 9960


def test_negative_temperature() -> None:
    """Test that the temperature is signed."""
    payload = bytearray(GAS_PAYLOAD)
    payload[14:16] = (-512).to_bytes(2, "little", signed=True)
    reading = parse_advertisement(GAS_ADDRESS, bytes(payload))
    assert reading is not None
    assert reading.temperature == -5.12


def test_unknown_model() -> None:
    """Test that unknown models of a known type still get a name."""
    payload = bytearray(WATER_PAYLOAD)
    payload[5] = 0x42
    reading = parse_advertisement("B0:42:02:00:26:E8", bytes(payload))
    assert reading is not None
    assert reading.model == "Water 66"


@pytest.mark.parametrize(
    ("address", "payload"),
    [
        # Constant blob sent from the B1 address.
        ("B1:01:02:00:26:E8", WATER_B1_PAYLOAD),
        # Serial in the address does not match the payload.
        ("B0:01:02:00:26:E1", WATER_PAYLOAD),
        # Meter type in the address does not match the payload.
        ("B0:01:01:00:26:E8", WATER_PAYLOAD),
        # Truncated payload.
        (WATER_ADDRESS, WATER_PAYLOAD[:16]),
        # Wrong marker.
        (WATER_ADDRESS, b"\x81" + WATER_PAYLOAD[1:]),
        # Unsupported meter type (electricity).
        ("B0:01:03:00:26:E8", WATER_PAYLOAD[:4] + b"\x03" + WATER_PAYLOAD[5:]),
    ],
)
def test_rejected(address: str, payload: bytes) -> None:
    """Test that foreign or inconsistent packets are ignored."""
    assert parse_advertisement(address, payload) is None
