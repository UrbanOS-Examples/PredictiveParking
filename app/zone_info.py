import json
import warnings
from io import BytesIO
from os import path

import pandas as pd
import requests

warnings.warn('The zone_info module is no longer in service and will be removed soon™.', DeprecationWarning, stacklevel=2)

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


def zone_ids():
    return ZONE_CLUSTER.zoneID.map(str).tolist()


def meter_and_zone_list():
    return _get_meter_and_zone_list_from_api()


def _get_meter_and_zone_list_from_api():
    DISCOVERY_API_QUERY_URL = 'https://data.smartcolumbusos.com/api/v1/query'
    METER_TO_ZONE_LIST_QUERY = '''
        WITH
            padded_meter_ids AS (
                SELECT
                    CONCAT(
                        REGEXP_EXTRACT("meter number", '\D+'),
                        LPAD(regexp_extract("meter number", '\d+'), 10, '0')
                    ) AS meter_id,
                    subareaname,
                    "meter number"
                FROM ips_group__parking_meter_inventory_2020
            ),
            padded_fybr_meter_ids AS (
                SELECT
                    CONCAT(
                        REGEXP_EXTRACT(name, '\D+'),
                        LPAD(REGEXP_EXTRACT(name, '\d+'), 10, '0')
                    ) AS meter_id,
                    id,
                    name
                FROM fybr__short_north_parking_sensor_sites
            )
        SELECT
            id AS meter_id,
            subareaname AS zone_id
        FROM padded_meter_ids ips JOIN padded_fybr_meter_ids fybr
            ON ips.meter_id = fybr.meter_id
    '''
    with requests.post(DISCOVERY_API_QUERY_URL, stream=True, params={'_format': 'json'}, data=METER_TO_ZONE_LIST_QUERY) as r:
        r.raise_for_status()
        with BytesIO() as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

            f.seek(0)
            response_json = f.read()

    return json.loads(response_json)