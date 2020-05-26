import datetime
from dateutil import tz, parser
import types

from functools import reduce
from itertools import starmap
from copy import deepcopy


INVALID_AFTER_MINUTES = 15


def availability(zone_index, zone_id, timestamp):
  def _too_old(_id, details):
    last_seen = details['last_seen']
    if not last_seen:
       return True
       
    cutoff = timestamp - datetime.timedelta(minutes=INVALID_AFTER_MINUTES)

    return last_seen < cutoff

  all_meters = zone_index.get(zone_id, {}).get('meters', {})

  if not all_meters or any(starmap(_too_old, all_meters.items())):
    return None

  all_meters_count = len(all_meters)
  available_meters = [m for (m, d) in all_meters.items() if d['occupied'] == False]
  available_meters_count = len(available_meters)

  return round(available_meters_count / all_meters_count, 4)


def create_message_handler(meter_index):
  def _reducer(index, message):
    if not message['event'] == 'update':
      return index

    record = message['payload']
    meter_id = record['id']

    zone_id = meter_index.get(meter_id)
    if not zone_id:
      return index

    last_seen = parser.isoparse(record['time_of_ingest']).replace(tzinfo=tz.tzutc())
    occupied = record['occupancy'] == 'OCCUPIED'

    index[zone_id]['meters'][meter_id] = {
      'occupied': occupied,
      'last_seen': last_seen
    }
    return index

  def _handler(messages, zone_index):
    return reduce(_reducer, messages, zone_index)

  return _handler


def _extract_meter_mapping(index, meter_row):
  meter_id = meter_row['meter_id']
  zone_id = meter_row['zone_id']

  index[meter_id] = zone_id

  return index


def _extract_zone_mappings(index, meter_row):
  meter_id = meter_row['meter_id']
  zone_id = meter_row['zone_id']

  current_zone = index.get(zone_id, {'meters': {}})
  current_zone_meters = current_zone.get('meters')

  current_zone_meters[meter_id] = {
    'occupied': None,
    'last_seen': None
  }

  current_zone['meters'] = current_zone_meters
  index[zone_id] = current_zone

  return index


def create_tracking_indices(meter_and_zone_list):
  meter_index = reduce(_extract_meter_mapping, meter_and_zone_list, {})
  zone_index = reduce(_extract_zone_mappings, meter_and_zone_list, {})

  return (zone_index, meter_index)