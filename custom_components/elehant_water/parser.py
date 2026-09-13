"""Decoder for Elehant meter BLE advertisements.

Elehant meters never accept connections; they only broadcast advertisements
from addresses of the form ``<prefix>:<model>:<type>:<serial, 3 bytes big
endian>``. Prefixes ``B0`` and ``C0`` carry readings, ``B1`` carries encrypted
data that only the vendor's server can read (ignored).

Manufacturer specific data (company id 0xFFFF stripped, as Home Assistant
delivers it) is 17 bytes, little endian unless noted. The header is common:

====== ====== ===========================================================
offset size   meaning
====== ====== ===========================================================
0      1      flags: 0x80 - valid packet, 0x04 - high resolution counter
3      1      packet version, selects the layout of bytes 9-16
4      1      meter type, same as in the address
5      1      meter model, same as in the address
6      3      serial number, same as in the address
====== ====== ===========================================================

Packet versions, as handled by the official Elehant app:

* 1 (gas, water, heat): counter (u32, 0.0001 m³ or GJ; byte 2 low nibble adds
  tenths of a unit when flag 0x04 is set), battery (byte 13), temperature
  (s16, 0.01 °C), firmware (byte 16, tenths).
* 5 (two-tariff water): battery (byte 1), temperature (byte 2, °C), two 28-bit
  big endian counters in 0.001 m³: high/low nibbles of byte 9 plus bytes
  10-12 and 13-15; the second counter belongs to the paired tariff model.
* 8: consumption history (ignored).
* 9: coolant volume (u32, 0.0001 m³), inlet and outlet temperature
  (u16, 0.01 °C).
* Electricity meters (type 3) rotate packet versions 0-49 carrying energy
  totals and tariffs, voltages, currents and powers, see
  :func:`_parse_electricity`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import IntEnum
import re

MANUFACTURER_ID = 0xFFFF

_VALID_FLAG = 0x80
_HIGH_RESOLUTION_FLAG = 0x04
_ADDRESS_PREFIXES = (0xB0, 0xC0)
_PAYLOAD_LENGTH = 17
_MAC_RE = re.compile(r"^[0-9A-F]{2}(:[0-9A-F]{2}){5}$", re.IGNORECASE)

# Sensor keys. They are part of entity unique ids, never change them.
VOLUME = "volume"
ENERGY = "energy"
COOLANT_VOLUME = "coolant_volume"
TEMPERATURE = "temperature"
TEMPERATURE_INLET = "temperature_inlet"
TEMPERATURE_OUTLET = "temperature_outlet"
BATTERY = "battery"
ENERGY_IMPORT = "energy_import"
ENERGY_EXPORT = "energy_export"
REACTIVE_ENERGY_IMPORT = "reactive_energy_import"
REACTIVE_ENERGY_EXPORT = "reactive_energy_export"
VOLTAGE = "voltage"
CURRENT = "current"
NEUTRAL_CURRENT = "neutral_current"
DIFFERENTIAL_CURRENT = "differential_current"
APPARENT_POWER = "apparent_power"
ACTIVE_POWER = "active_power"
REACTIVE_POWER = "reactive_power"
FREQUENCY = "frequency"
POWER_FACTOR = "power_factor"


def tariff_key(key: str, tariff: int) -> str:
    """Return the key of a per-tariff value."""
    return f"{key}_tariff_{tariff}"


def phase_key(key: str, phase: str) -> str:
    """Return the key of a per-phase value (``a`` or line ``ab``)."""
    return f"{key}_{phase}"


class MeterType(IntEnum):
    """Kind of the metered resource."""

    GAS = 1
    WATER = 2
    ELECTRICITY = 3
    HEAT = 4


@dataclass(frozen=True, slots=True)
class ModelInfo:
    """Properties of a meter model, as described by the official app."""

    name: str
    temperature: bool = False
    """Whether the temperature field is meaningful."""
    temperature_firmware_exceptions: frozenset[int] = frozenset()
    """Firmware versions (tenths) that invert ``temperature``."""
    tariff: int | None = None
    """Tariff number for two-tariff models reporting each tariff separately."""
    paired_model: int | None = None
    """Model id reporting the other tariff of the same meter."""

    def has_temperature(self, firmware: int) -> bool:
        """Return whether the temperature is valid for the firmware."""
        return self.temperature != (firmware in self.temperature_firmware_exceptions)


HAS_BATTERY: dict[MeterType, bool] = {
    MeterType.GAS: True,
    MeterType.WATER: True,
    MeterType.ELECTRICITY: False,
    MeterType.HEAT: True,
}


def _tariff_pair(name: str, first: int, second: int) -> dict[int, ModelInfo]:
    return {
        first: ModelInfo(name, temperature=True, tariff=1, paired_model=second),
        second: ModelInfo(name, temperature=True, tariff=2, paired_model=first),
    }


MODELS: dict[MeterType, dict[int, ModelInfo]] = {
    MeterType.GAS: {
        model: ModelInfo(name)
        for model, name in {
            1: "СГБ-1.8",
            2: "СГБ-3.2",
            3: "СГБ-4.0",
            4: "СГБ-6.0",
            5: "СГБ-1.6",
            16: "СГБД-1.8",
            17: "СГБД-3.2",
            18: "СГБД-4.0",
            19: "СГБД-6.0",
            20: "СГБД-1.6",
            32: "СОНИК-G1.6",
            33: "СОНИК-G2.5",
            34: "СОНИК-G4",
            35: "СОНИК-G6",
            36: "СОНИК-G10",
            48: "СГБД-1.8ТК",
            49: "СГБД-3.2ТК",
            50: "СГБД-4.0ТК",
            51: "СГБД-6.0ТК",
            52: "СГБД-1.6ТК",
            64: "СОНИК-G1.6ТК",
            65: "СОНИК-G2.5ТК",
            66: "СОНИК-G4ТК",
            67: "СОНИК-G6ТК",
            68: "СОНИК-G10ТК",
            80: "СГБ-1.8ТК",
            81: "СГБ-3.2ТК",
            82: "СГБ-4.0ТК",
            83: "СГБ-6.0ТК",
            84: "СГБ-1.6ТК",
        }.items()
    },
    MeterType.WATER: {
        1: ModelInfo(
            "СВД-15",
            temperature=True,
            temperature_firmware_exceptions=frozenset({14, 16, 17, 18}),
        ),
        2: ModelInfo(
            "СВД-20",
            temperature=True,
            temperature_firmware_exceptions=frozenset({14, 16, 17, 18, 19}),
        ),
        **_tariff_pair("СВТ-15", 4, 3),
        **_tariff_pair("СВТ-20", 6, 5),
        7: ModelInfo("СВДУ-15"),
        8: ModelInfo("СВДУ-20"),
        **_tariff_pair("СВТУ-15", 10, 9),
        **_tariff_pair("СВТУ-20", 12, 11),
        13: ModelInfo("SWTU-15"),
        14: ModelInfo("SWTU-20"),
        **_tariff_pair("TWM-15", 16, 15),
        **_tariff_pair("TWM-20", 18, 17),
    },
    MeterType.ELECTRICITY: {
        1: ModelInfo("МИР С-01"),
        4: ModelInfo("МИР С-04"),
        5: ModelInfo("МИР С-05"),
        7: ModelInfo("МИР С-07"),
    },
    MeterType.HEAT: {
        1: ModelInfo("СТЭ", temperature=True),
    },
}


@dataclass(frozen=True, slots=True)
class ElehantReading:
    """Values decoded from a single advertisement."""

    meter_type: MeterType
    model_id: int
    serial: int
    packet_version: int
    firmware: str | None
    values: Mapping[str, float] = field(default_factory=dict)

    @property
    def model_info(self) -> ModelInfo:
        """Return the properties of the meter model."""
        return MODELS[self.meter_type][self.model_id]

    @property
    def model(self) -> str:
        """Return the human readable model name."""
        return self.model_info.name

    @property
    def title(self) -> str:
        """Return a name identifying the advertising meter."""
        title = f"{self.model} {self.serial}"
        if (tariff := self.model_info.tariff) and self.packet_version != 5:
            # Unless both tariffs come in one packet, each tariff is advertised
            # from its own address.
            title = f"{title}, тариф {tariff}"
        return title


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little")


def _battery(raw: int, max_valid: int) -> int:
    """Convert the battery byte the way the official app does."""
    if raw < 1 or raw > max_valid:
        # Out of range readings are shown as an almost empty battery.
        return 1
    return min(raw, 100)


def parse_address(address: str) -> tuple[MeterType, int, int] | None:
    """Return the meter type, model id and serial encoded in a MAC address."""
    if not _MAC_RE.match(address):
        return None
    mac = bytes.fromhex(address.replace(":", ""))
    if mac[0] not in _ADDRESS_PREFIXES:
        return None
    try:
        meter_type = MeterType(mac[2])
    except ValueError:
        return None
    return meter_type, mac[1], int.from_bytes(mac[3:6], "big")


def parse_meter(address: str, data: bytes) -> ElehantReading | None:
    """Identify a supported meter from any of its packets, without values.

    ``address`` is used only for a consistency check when it is a MAC address
    (macOS exposes random UUIDs instead of MAC addresses).
    """
    if len(data) < _PAYLOAD_LENGTH or not data[0] & _VALID_FLAG:
        return None
    try:
        meter_type = MeterType(data[4])
    except ValueError:
        return None
    model_id = data[5]
    serial = int.from_bytes(data[6:9], "little")
    if serial == 0 or model_id not in MODELS[meter_type]:
        return None

    if _MAC_RE.match(address) and parse_address(address) != (
        meter_type,
        model_id,
        serial,
    ):
        return None

    return ElehantReading(
        meter_type=meter_type,
        model_id=model_id,
        serial=serial,
        packet_version=data[3],
        firmware=None,
    )


def parse_advertisement(address: str, data: bytes) -> ElehantReading | None:
    """Decode Elehant manufacturer data, return None for unsupported packets."""
    if (meter := parse_meter(address, data)) is None:
        return None
    meter_type, info, version = meter.meter_type, meter.model_info, meter.packet_version
    firmware: int | None = None
    if meter_type is MeterType.ELECTRICITY:
        values = _parse_electricity(version, data)
    elif version == 1:
        firmware = data[16]
        values = _parse_v1(meter_type, info, data)
    elif version == 5 and meter_type is MeterType.WATER:
        firmware = data[16]
        values = _parse_v5(meter_type, info, data)
    elif version == 9:
        values = _parse_v9(data)
    else:
        return None
    if values is None:
        return None

    return replace(
        meter,
        firmware=f"{firmware / 10:.1f}" if firmware else None,
        values=values,
    )


def parse_manufacturer_data(
    address: str, manufacturer_data: Mapping[int, bytes]
) -> ElehantReading | None:
    """Decode the Elehant entry of an advertisement's manufacturer data."""
    if (data := manufacturer_data.get(MANUFACTURER_ID)) is None:
        return None
    return parse_advertisement(address, data)


def identify_meter(
    address: str, manufacturer_data: Mapping[int, bytes]
) -> ElehantReading | None:
    """Identify the meter sending an advertisement's manufacturer data."""
    if (data := manufacturer_data.get(MANUFACTURER_ID)) is None:
        return None
    return parse_meter(address, data)


def _parse_v1(meter_type: MeterType, info: ModelInfo, data: bytes) -> dict[str, float]:
    counter: float = _u32(data, 9)
    if data[0] & _HIGH_RESOLUTION_FLAG:
        counter += (data[2] & 0x0F) / 10
    values: dict[str, float] = {
        ENERGY if meter_type is MeterType.HEAT else VOLUME: counter / 10000
    }
    if HAS_BATTERY[meter_type]:
        values[BATTERY] = _battery(data[13], 171)
    if info.has_temperature(data[16]):
        values[TEMPERATURE] = int.from_bytes(data[14:16], "little", signed=True) / 100
    return values


def _parse_v5(meter_type: MeterType, info: ModelInfo, data: bytes) -> dict[str, float]:
    own = (data[9] >> 4) << 24 | int.from_bytes(data[10:13], "big")
    paired = (data[9] & 0x0F) << 24 | int.from_bytes(data[13:16], "big")
    own_tariff = info.tariff or 1
    paired_tariff = 2 if own_tariff == 1 else 1
    values: dict[str, float] = {
        tariff_key(VOLUME, own_tariff): own / 1000,
        tariff_key(VOLUME, paired_tariff): paired / 1000,
    }
    if HAS_BATTERY[meter_type]:
        values[BATTERY] = _battery(data[1], 127)
    if info.has_temperature(data[16]):
        values[TEMPERATURE] = data[2]
    return values


def _parse_v9(data: bytes) -> dict[str, float]:
    return {
        COOLANT_VOLUME: _u32(data, 9) / 10000,
        TEMPERATURE_INLET: _u16(data, 13) / 100,
        TEMPERATURE_OUTLET: _u16(data, 15) / 100,
    }


def _parse_electricity(version: int, data: bytes) -> dict[str, float] | None:
    """Decode one of the rotating electricity meter packets."""
    first, second = _u32(data, 9), _u32(data, 13)
    match version:
        case 0:
            return {ENERGY_IMPORT: first / 1000, ENERGY_EXPORT: second / 1000}
        case 1 | 2 | 3 | 4:
            return {
                tariff_key(ENERGY_IMPORT, version): first / 1000,
                tariff_key(ENERGY_EXPORT, version): second / 1000,
            }
        case 16:
            return {
                REACTIVE_ENERGY_IMPORT: first / 1000,
                REACTIVE_ENERGY_EXPORT: second / 1000,
            }
        case 17 | 18 | 19 | 20:
            return {
                tariff_key(REACTIVE_ENERGY_IMPORT, version - 16): first / 1000,
                tariff_key(REACTIVE_ENERGY_EXPORT, version - 16): second / 1000,
            }
        case 32:
            return {
                VOLTAGE: _u16(data, 9) / 10,
                CURRENT: _u16(data, 11) / 100,
                NEUTRAL_CURRENT: _u16(data, 13) / 100,
                DIFFERENTIAL_CURRENT: _u16(data, 15) / 100,
            }
        case 33:
            return {
                phase_key(VOLTAGE, phase): _u16(data, offset) / 10
                for phase, offset in (("a", 9), ("b", 11), ("c", 13))
            }
        case 34:
            return {
                phase_key(VOLTAGE, phase): _u16(data, offset) / 10
                for phase, offset in (("ab", 9), ("bc", 11), ("ca", 13))
            }
        case 35:
            return {
                **{
                    phase_key(CURRENT, phase): _u16(data, offset) / 100
                    for phase, offset in (("a", 9), ("b", 11), ("c", 13))
                },
                NEUTRAL_CURRENT: _u16(data, 15) / 100,
            }
        case 48:
            return {
                APPARENT_POWER: first / 100,
                FREQUENCY: _u16(data, 13) / 100,
                POWER_FACTOR: data[15] / 100,
            }
        case 49:
            return {ACTIVE_POWER: first / 100, REACTIVE_POWER: second / 100}
    return None
