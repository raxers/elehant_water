"""Decoder for Elehant meter BLE advertisements.

Elehant meters (СВД/СВТ water meters, СГБ/СГБД/СОНИК gas meters) never accept
connections; they only broadcast advertisements. Every meter uses two
addresses:

* ``B0:<model>:<type>:<serial, 3 bytes big endian>`` carries the readings;
* ``B1:<model>:<type>:<serial>`` carries an opaque, constant blob (ignored).

Manufacturer specific data of the ``B0`` packet (company id 0xFFFF stripped,
as Home Assistant delivers it), little endian:

====== ====== ===========================================================
offset size   meaning
====== ====== ===========================================================
0      1      always 0x80
1      1      packet sequence counter
2      1      unknown
3      1      packet format version
4      1      meter type (1 - gas, 2 - water), same as in the address
5      1      meter model, same as in the address
6      3      serial number, same as in the address
9      4      counter, 0.1 litre units
13     1      battery level, percent (values above 100 are reported)
14     2      temperature, 0.01 °C, signed
16     1      firmware version, tenths
====== ====== ===========================================================

The layout was reverse engineered by the community, see
https://github.com/vooon/elehant-to-mqtt/blob/master/docs/protocol.md
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum
import re

MANUFACTURER_ID = 0xFFFF
PAYLOAD_MARKER = 0x80

_ADDRESS_PREFIX = 0xB0
_MIN_PAYLOAD_LENGTH = 17
_MAC_RE = re.compile(r"^[0-9A-F]{2}(:[0-9A-F]{2}){5}$", re.IGNORECASE)


class MeterType(IntEnum):
    """Kind of the metered resource."""

    GAS = 1
    WATER = 2


MODEL_NAMES: dict[tuple[MeterType, int], str] = {
    (MeterType.GAS, 1): "СГБ-1.8",
    (MeterType.GAS, 2): "СГБ-3.2",
    (MeterType.GAS, 3): "СГБ-4.0",
    (MeterType.GAS, 4): "СГБ-6.0",
    (MeterType.GAS, 5): "СГБ-1.6",
    (MeterType.GAS, 16): "СГБД-1.8",
    (MeterType.GAS, 17): "СГБД-3.2",
    (MeterType.GAS, 18): "СГБД-4.0",
    (MeterType.GAS, 19): "СГБД-6.0",
    (MeterType.GAS, 20): "СГБД-1.6",
    (MeterType.GAS, 32): "СОНИК-G1.6",
    (MeterType.GAS, 33): "СОНИК-G2.5",
    (MeterType.GAS, 34): "СОНИК-G4",
    (MeterType.GAS, 35): "СОНИК-G6",
    (MeterType.GAS, 36): "СОНИК-G10",
    (MeterType.GAS, 48): "СГБД-1.8ТК",
    (MeterType.GAS, 49): "СГБД-3.2ТК",
    (MeterType.GAS, 50): "СГБД-4.0ТК",
    (MeterType.GAS, 51): "СГБД-6.0ТК",
    (MeterType.GAS, 52): "СГБД-1.6ТК",
    (MeterType.GAS, 64): "СОНИК-G1.6ТК",
    (MeterType.GAS, 65): "СОНИК-G2.5ТК",
    (MeterType.GAS, 66): "СОНИК-G4ТК",
    (MeterType.GAS, 67): "СОНИК-G6ТК",
    (MeterType.GAS, 68): "СОНИК-G10ТК",
    (MeterType.GAS, 80): "СГБ-1.8ТК",
    (MeterType.GAS, 81): "СГБ-3.2ТК",
    (MeterType.GAS, 82): "СГБ-4.0ТК",
    (MeterType.GAS, 83): "СГБ-6.0ТК",
    (MeterType.GAS, 84): "СГБ-1.6ТК",
    (MeterType.WATER, 1): "СВД-15",
    (MeterType.WATER, 2): "СВД-20",
    (MeterType.WATER, 3): "СВТ-15",
    (MeterType.WATER, 4): "СВТ-15",
    (MeterType.WATER, 5): "СВТ-20",
    (MeterType.WATER, 6): "СВТ-20",
}


@dataclass(frozen=True, slots=True)
class ElehantReading:
    """Values decoded from a single advertisement."""

    meter_type: MeterType
    model_id: int
    serial: int
    volume: float
    """Total volume in cubic meters."""
    temperature: float
    """Temperature in °C."""
    battery: int
    firmware: str | None

    @property
    def model(self) -> str:
        """Return the human readable model name."""
        return MODEL_NAMES.get(
            (self.meter_type, self.model_id),
            f"{self.meter_type.name.title()} {self.model_id}",
        )

    @property
    def title(self) -> str:
        """Return a name identifying the meter."""
        return f"{self.model} {self.serial}"


def parse_advertisement(address: str, data: bytes) -> ElehantReading | None:
    """Decode Elehant manufacturer data, return None for foreign packets.

    ``address`` is used only for a consistency check when it is a MAC address
    (macOS exposes random UUIDs instead of MAC addresses).
    """
    if len(data) < _MIN_PAYLOAD_LENGTH or data[0] != PAYLOAD_MARKER:
        return None
    try:
        meter_type = MeterType(data[4])
    except ValueError:
        return None
    model_id = data[5]
    serial = int.from_bytes(data[6:9], "little")

    if _MAC_RE.match(address):
        mac = bytes.fromhex(address.replace(":", ""))
        if (
            mac[0] != _ADDRESS_PREFIX
            or mac[1] != model_id
            or mac[2] != meter_type
            or int.from_bytes(mac[3:6], "big") != serial
        ):
            return None

    return ElehantReading(
        meter_type=meter_type,
        model_id=model_id,
        serial=serial,
        volume=int.from_bytes(data[9:13], "little") / 10000,
        temperature=int.from_bytes(data[14:16], "little", signed=True) / 100,
        battery=min(data[13], 100),
        firmware=f"{data[16] / 10:.1f}" if data[16] else None,
    )


def parse_manufacturer_data(
    address: str, manufacturer_data: Mapping[int, bytes]
) -> ElehantReading | None:
    """Decode the Elehant entry of an advertisement's manufacturer data."""
    if (data := manufacturer_data.get(MANUFACTURER_ID)) is None:
        return None
    return parse_advertisement(address, data)
