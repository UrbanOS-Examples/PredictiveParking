from os import path
import pandas as pd
import logging
import requests
import json

from io import BytesIO


DISCOVERY_API_QUERY_URL='https://data.smartcolumbusos.com/api/v1/query'
METER_TO_ZONE_LIST_QUERY = '''
with padded_meter_ids as (
select concat(regexp_extract("meter number", '\D+'), lpad(regexp_extract("meter number", '\d+'), 10, '0')) as meter_id, subareaname, "meter number" from ips_group__parking_meter_inventory_2020
),
padded_fybr_meter_ids as(
select concat(regexp_extract(name, '\D+'), lpad(regexp_extract(name, '\d+'), 10, '0')) as meter_id, id, name from  fybr__short_north_parking_sensor_sites
)
SELECT id as meter_id, subareaname as zone_id FROM padded_fybr_meter_ids f join padded_meter_ids i on f.meter_id = i.meter_id
'''

def _get_meter_and_zone_list_from_api():
    with requests.post(DISCOVERY_API_QUERY_URL, stream=True, params={'_format': 'json'}, data=METER_TO_ZONE_LIST_QUERY) as r:
        r.raise_for_status()
        with BytesIO() as f:
            for chunk in r.iter_content(chunk_size=8192): 
                f.write(chunk)

            f.seek(0)
            response_json = f.read()

    return json.loads(response_json)


DIRNAME = path.dirname(path.abspath(__file__))
METER_FILE_PATH = path.join(
  DIRNAME,
  'meter_config',
  'zone_cluster16_short_north_downtown_15_19.csv'
)
ZONE_CLUSTER = pd.read_csv(METER_FILE_PATH)


def cluster_ids():
  return ZONE_CLUSTER.clusterID.unique().tolist()


def zone_cluster():
  return ZONE_CLUSTER


def meter_and_zone_list():
  return _get_meter_and_zone_list_from_api()

