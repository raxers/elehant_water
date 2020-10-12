from time import sleep
from datetime import timedelta, datetime
import aioblescan as aiobs
import asyncio
import time
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
import random
import logging
from homeassistant.const import (VOLUME_LITERS, STATE_UNKNOWN)

_LOGGER = logging.getLogger(__name__)
inf={}

def update_counters(call):
    global scan_duration
    def my_process(data):
        if time.time()-start >int(scan_duration):
            btctrl.stop_scan_request()
            conn.close()
            event_loop.stop()
        ev=aiobs.HCI_Event()
        xx = ev.decode(data)
        try:
            mac = ev.retrieve("peer")[0].val
        except:
            return
        if str(mac).find('b0:01:02') !=-1:
            manufacturer_data = ev.retrieve("Manufacturer Specific Data")   
            payload = manufacturer_data[0].payload
            payload = payload[1].val     
            c_num = int.from_bytes(payload[6:8], byteorder='little')
            c_count = int.from_bytes(payload[9:12], byteorder='little')
            inf[c_num] = c_count/10
    start = time.time()
    event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(event_loop)
    mysocket = aiobs.create_bt_socket(0)
    fac=event_loop._create_connection_transport(mysocket,aiobs.BLEScanRequester,None,None)
    conn,btctrl = event_loop.run_until_complete(fac)
    btctrl.process=my_process
    btctrl.send_scan_request()

    try:
        event_loop.run_forever()
    except KeyboardInterrupt:
        print('keyboard interrupt')
    finally:
        print('closing event loop')
        btctrl.stop_scan_request()
        conn.close()
        event_loop.close()

        
def setup_platform(hass, config, add_entities, discovery_info=None):
    global scan_interval, scan_duration
    ha_entities=[]
    _LOGGER.error(config)
    scan_interval = config['scan_interval']
    scan_duration = config['scan_duration']
    for device in config['devices']:        
        ha_entities.append(ExampleSensor(device['id'],device['name']))
        inf[device['id']]=STATE_UNKNOWN
    add_entities(ha_entities, True)
    async_track_time_interval(
        hass, update_counters, scan_interval
    )
    


class ExampleSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self,counter_num, name):
        """Initialize the sensor."""
        self._state = None
        self._name = name
        self._state = STATE_UNKNOWN
        self._num  = counter_num


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
        return VOLUME_LITERS
    @property
    def icon(self):
        """Return the unit of measurement."""
        return 'mdi:water-pump'
    @property
    def unique_id(self):
        """Return Unique ID """
        return 'elehant_'+str(self._num)

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """  
        # update_counters()              
        self._state = inf[self._num]
