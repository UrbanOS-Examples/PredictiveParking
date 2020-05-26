from dateutil import parser, tz
from contextlib import contextmanager

from app import availability_provider

@contextmanager
def set_availability_zone_index(meter_and_zone_list):
    availability_provider.set_zone_index(meter_and_zone_list)
    yield
    availability_provider.set_zone_index([])


def as_ts(iso_string):
  return parser.isoparse(iso_string).replace(tzinfo=tz.tzutc())