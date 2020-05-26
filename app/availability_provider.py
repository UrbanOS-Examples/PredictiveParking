import json
import websockets
import backoff
from datetime import datetime
from dateutil import tz
from copy import deepcopy

from app import availability_tracker
from app import zone_info


STATE = {
  'zone_index': {},
  'meter_index': {}
}

DATASET_STREAM_SYSTEM_NAME = 'fybr__short_north_parking_occupancy'
DATASET_STREAM_URI = 'wss://streams.smartcolumbusos.com/socket/websocket'
JOIN_MESSAGE = json.dumps({
  "topic": f"streaming:{DATASET_STREAM_SYSTEM_NAME}",
  "event": "phx_join",
  "payload": {},
  "ref":"1"
})


async def listen_to_stream_forever():
  set_zone_index(zone_info.meter_and_zone_list())

  await handle_websocket_messages(DATASET_STREAM_URI)


def set_zone_index(meter_and_zone_list):
  (zone_index, meter_index) = availability_tracker.create_tracking_indices(meter_and_zone_list)

  _set_state('zone_index', zone_index)
  _set_state('meter_index', meter_index)


def get_all_availability():
  availabilities = {}
  now = datetime.now(tz.tzutc())
  zone_index = _get_state('zone_index')

  for zone_id in zone_index:
    availability = availability_tracker.availability(zone_index, zone_id, now)
    if availability != None:
      availabilities[zone_id] = availability

  return availabilities


def _log_exception(details):
    print("Backing off {wait:0.1f} seconds afters {tries} tries "
           "calling function {target} with args {args} and kwargs "
           "{kwargs}".format(**details))

  
@backoff.on_exception(backoff.expo,
                      Exception,
                      on_backoff=_log_exception)
async def handle_websocket_messages(uri):
  async with websockets.connect(uri) as websocket:
    await websocket.send(JOIN_MESSAGE)

    handler = availability_tracker.create_message_handler(_get_state('meter_index'))

    async for message_string in websocket:
      message = json.loads(message_string)
      _set_state(
        'zone_index',
        handler([message], _get_state('zone_index'))
      )

    
def _get_state(key):
  return deepcopy(STATE[key])


def _set_state(key, value):
  STATE[key] = value