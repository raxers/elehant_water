from time import sleep
from datetime import timedelta, datetime
import aioblescan as aiobs
import asyncio
import time
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval
import random
import logging
from homeassistant.const import (
    VOLUME_LITERS,
    STATE_UNKNOWN,
    VOLUME_CUBIC_METERS,
    TEMP_CELSIUS,
)

_LOGGER = logging.getLogger("elehant_water")
inf = {}
_LOGGER.debug("init")


def update_counters(call):
    global scan_duration, current_event_loop

    def my_process(data):
        ev = aiobs.HCI_Event()
        xx = ev.decode(data)
        try:
            mac = ev.retrieve("peer")[0].val
        except:
            return

        """СГБТ-1.8"""
        if (str(mac).find('b0:10:01') !=-1) or (str(mac).find('b0:11:01') !=-1) or (str(mac).find('b0:12:01') !=-1):
            _LOGGER.debug("SEE gaz counter")
            manufacturer_data = ev.retrieve("Manufacturer Specific Data")
            payload = manufacturer_data[0].payload
            payload = payload[1].val
            c_num = int.from_bytes(payload[6:8], byteorder='little')
            c_count = int.from_bytes(payload[9:12], byteorder='little')
            if measurement_gas == 'm3':
                inf[c_num] = c_count/10000
            else:
                inf[c_num] = c_count/10

        """СВД-15, СВД-20"""
        if (str(mac).find('b0:01:02') !=-1) or (str(mac).find('b0:02:02') !=-1):
            _LOGGER.debug("SEE 1 tariff counter")
            manufacturer_data = ev.retrieve("Manufacturer Specific Data")
            payload = manufacturer_data[0].payload
            payload = payload[1].val
            c_num = int.from_bytes(payload[6:8], byteorder="little")
            c_count = int.from_bytes(payload[9:12], byteorder="little")
            if measurement_water == "m3":
                inf[c_num] = c_count / 10000
            else:
                inf[c_num] = c_count / 10

        """СВТ-15 холодная, СВТ-15 горячая, СВТ-20 холодная, СВТ-20 горячая"""
        if (str(mac).find('b0:03:02') !=-1) or (str(mac).find('b0:04:02') !=-1) or (str(mac).find('b0:05:02') !=-1) or (str(mac).find('b0:06:02') !=-1):
            _LOGGER.debug("SEE 2 tariff counter")
            manufacturer_data = ev.retrieve("Manufacturer Specific Data")
            payload = manufacturer_data[0].payload
            payload = payload[1].val
            c_num = int.from_bytes(payload[6:8], byteorder="little")
            if (str(mac).find('b0:03:02') !=-1) or (str(mac).find('b0:05:02') !=-1):
                c_num = str(c_num) + "_1"
            else:
                c_num = str(c_num) + "_2"
            c_count = int.from_bytes(payload[9:12], byteorder="little")
            c_temp = int.from_bytes(payload[14:16], byteorder="little") / 100
            inf[c_num.split("_")[0]] = c_temp
            if measurement_water == "m3":
                inf[c_num] = c_count / 10000
            else:
                inf[c_num] = c_count / 10

    if current_event_loop is None:
        current_event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(current_event_loop)
    mysocket = aiobs.create_bt_socket(0)
    fac = getattr(current_event_loop, "_create_connection_transport")(
        mysocket, aiobs.BLEScanRequester, None, None
    )
    conn, btctrl = current_event_loop.run_until_complete(fac)
    btctrl.process = my_process
    current_event_loop.run_until_complete(btctrl.send_scan_request(scan_duration))
    try:
        current_event_loop.run_forever()
    finally:
        current_event_loop(btctrl.stop_scan_request())
        conn.close()
        current_event_loop.run_until_complete(asyncio.sleep(0))

        current_event_loop.close()


def setup_platform(hass, config, add_entities, discovery_info=None):
    global scan_interval, scan_duration, measurement_water, measurement_gas, current_event_loop
    ha_entities = []
    scan_interval = config["scan_interval"]
    scan_duration = config["scan_duration"]
    current_event_loop = None
    measurement_water = config.get("measurement_water")
    measurement_gas = config.get("measurement_gas")
    for device in config["devices"]:
        if device["type"] == "gas":
            ha_entities.append(GasSensor(device["id"], device["name"]))
            inf[device["id"]] = STATE_UNKNOWN
        else:
            ha_entities.append(WaterSensor(device["id"], device["name"]))
            if "_1" in str(device["id"]):
                ha_entities.append(
                    WaterTempSensor(device["id"].split("_")[0], device["name_temp"])
                )
                inf[device["id"].split("_")[0]] = STATE_UNKNOWN
            inf[device["id"]] = STATE_UNKNOWN

    add_entities(ha_entities, True)
    track_time_interval(hass, update_counters, scan_interval)


class WaterTempSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, counter_num, name):
        """Initialize the sensor."""
        self._state = None
        self._name = name
        self._state = STATE_UNKNOWN
        self._num = counter_num

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""

        return TEMP_CELSIUS

    @property
    def icon(self):
        """Return the unit of measurement."""
        return "mdi:thermometer-lines"

    @property
    def unique_id(self):
        """Return Unique ID"""
        return "elehant_temp_" + str(self._num)

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        # update_counters()
        self._state = inf[self._num]


class WaterSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, counter_num, name):
        """Initialize the sensor."""
        self._state = None
        self._name = name
        self._state = STATE_UNKNOWN
        self._num = counter_num

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if measurement_water == "m3":
            return VOLUME_CUBIC_METERS
        else:
            return VOLUME_LITERS

    @property
    def icon(self):
        """Return the unit of measurement."""
        return "mdi:water-pump"

    @property
    def unique_id(self):
        """Return Unique ID"""
        return "elehant_" + str(self._num)

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        # update_counters()
        self._state = inf[self._num]


class GasSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, counter_num, name):
        """Initialize the sensor."""
        self._state = None
        self._name = name
        self._state = STATE_UNKNOWN
        self._num = counter_num

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if measurement_gas == "m3":
            return VOLUME_CUBIC_METERS
        else:
            return VOLUME_LITERS

    @property
    def icon(self):
        """Return the unit of measurement."""
        return "mdi:gas-burner"

    @property
    def unique_id(self):
        """Return Unique ID"""
        return "elehant_" + str(self._num)

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        # update_counters()
        self._state = inf[self._num]
