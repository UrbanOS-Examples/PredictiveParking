import pytest
from tests.util import as_ts

from app import availability_tracker


def test_handler_reduces_applicable_messages_into_index():
  meter_index = {
    '9860': '0001',
    '9861': '0001',
    '9862': '0002',
    '9863': '0002'
  }

  zone_index = {
    '0001': {
      'meters': {
        '9860': {
          'occupied': None,
          'last_seen': None
        },
        '9861': {
          'occupied': None,
          'last_seen': None
        }
      }
    },
    '0002': {
      'meters': {
        '9862': {
          'occupied': None,
          'last_seen': None
        },
        '9863': {
          'occupied': None,
          'last_seen': None
        }
      }
    }
  }

  messages = [
    {"event":"update","payload":{"id":"9861","limit":"no-limit","occupancy":"OCCUPIED","time_of_ingest":"2020-05-21T18:00:00.037201"}},
    {"event": "presence_diff"},
    {"event":"update","payload":{"id":"9862","limit":"no-limit","occupancy":"UNOCCUPIED","time_of_ingest":"2020-05-21T18:01:00.037201"}},
    {"event":"update","payload":{"id":"9862","limit":"no-limit","occupancy":"OCCUPIED","time_of_ingest":"2020-05-21T18:01:00.037201"}},
    {"event": "presence_diff"},
    {"event":"update","payload":{"id":"9861","limit":"no-limit","occupancy":"UNOCCUPIED","time_of_ingest":"2020-05-21T18:01:00.037202"}},
    {"event":"update","payload":{"id":"9863","limit":"no-limit","occupancy":"UNOCCUPIED","time_of_ingest":"2020-05-21T18:01:00.037202"}}
  ]

  message_handler = availability_tracker.create_message_handler(meter_index)

  zone_index = message_handler(messages, zone_index)

  assert zone_index == {
    '0001': {
      'meters': {
        '9860': {
          'occupied': None,
          'last_seen': None
        },
        '9861': {
          'occupied': False,
          'last_seen': as_ts('2020-05-21T18:01:00.037202')
        }
      }
    },
    '0002': {
      'meters': {
        '9862': {
          'occupied': True,
          'last_seen': as_ts('2020-05-21T18:01:00.037201')
        },
        '9863': {
          'occupied': False,
          'last_seen': as_ts('2020-05-21T18:01:00.037202')
        }
      }
    }
  }


def test_occupancy_returns_valid_availability_for_zone_and_timestamp():
  timestamp_to_test = as_ts('2020-05-21T17:15:01.000000')

  zone_that_is_valid_because_all_data_is_within_last_15_minutes = {
    'meters': {
      '9864': {
        'occupied': True,
        'last_seen': as_ts('2020-05-21T17:14:00.032202')
      },
      '9865': {
        'occupied': False,
        'last_seen': as_ts('2020-05-21T17:12:00.037202')
      },
      '9866': {
        'occupied': False,
        'last_seen': as_ts('2020-05-21T17:11:00.037202')
      }
    }
  }
  zone_that_is_invalid_because_it_has_old_meter_data = {
    'meters': {
      '9862': {
        'occupied': True,
        'last_seen': as_ts('2020-05-21T17:00:00.000000')
      },
      '9863': {
        'occupied': False,
        'last_seen': as_ts('2020-05-21T16:01:00.037202')
      }
    }
  }
  zone_that_is_invalid_because_it_has_not_seen_a_meter = {
    'meters': {
      '9860': {
        'occupied': None,
        'last_seen': None
      },
      '9861': {
        'occupied': False,
        'last_seen': as_ts('2020-05-21T18:01:00.037202')
      }
    }
  }
  zone_that_is_invalid_because_it_has_no_meters = {
    'meters': {}
  }

  zone_index = {
    '0001': zone_that_is_invalid_because_it_has_not_seen_a_meter,
    '0002': zone_that_is_invalid_because_it_has_old_meter_data,
    '0003': zone_that_is_valid_because_all_data_is_within_last_15_minutes,
    '0004': zone_that_is_invalid_because_it_has_no_meters
  }

  assert None == availability_tracker.availability(zone_index, '0001', timestamp_to_test)
  assert None == availability_tracker.availability(zone_index, '0002', timestamp_to_test)
  assert round(0.6666, 2) == round(availability_tracker.availability(zone_index, '0003', timestamp_to_test), 2)
  assert None == availability_tracker.availability(zone_index, '0004', timestamp_to_test)
  assert None == availability_tracker.availability(zone_index, 'missing zone', timestamp_to_test)