import pytest
import json
import websockets
from freezegun import freeze_time
from contextlib import contextmanager

from tests.fake_websocket_server import create_fake_server, update_event
from app import app
from app.fybr.availability_provider import FybrAvailabilityProvider

pytestmark = pytest.mark.asyncio


async def test_no_zone_id_param_returns_all_zones(client):
    with freeze_time('2020-01-14 14:00:00'):
        response = await client.get('/api/v1/predictions')
        data = await response.get_data()

    assert response.status_code == 200
    assert len(json.loads(data)) > 0


async def test_zone_ids_restricts_zones(client):
    with freeze_time('2020-01-14 14:00:00'):
        response = await client.get('/api/v1/predictions?zone_ids=31004,31002')
        data = await response.get_data()

    assert response.status_code == 200
    assert len(json.loads(data)) == 2


async def test_empty_zone_ids_returns_no_predictions(client):
    with freeze_time('2020-01-14 14:00:00'):
        response = await client.get('/api/v1/predictions?zone_ids=')
        data = await response.get_data()

    assert response.status_code == 200
    assert len(json.loads(data)) == 0


async def test_only_invalid_zone_ids_does_not_return_predictions(client):
    with freeze_time('2020-01-14 14:00:00'):
        response = await client.get('/api/v1/predictions?zone_ids=WQRQWEQ,ETWERWER,QWEQWRQ')
        data = await response.get_data()

    assert response.status_code == 200
    assert len(json.loads(data)) == 0


async def test_mixed_invalid_and_valid_zone_ids_returns_predictions_for_valid(client):
    with freeze_time('2020-01-14 14:00:00'):
        response = await client.get('/api/v1/predictions?zone_ids=WQRQWEQ,31004,QWEQWRQ')
        data = await response.get_data()

    assert response.status_code == 200
    assert len(json.loads(data)) == 1


async def test_time_out_of_hours_returns_no_predictions(client):
    with freeze_time('2020-01-14 05:00:00'):
        response = await client.get('/api/v1/predictions')
        data = await response.get_data()

    assert response.status_code == 200
    assert len(json.loads(data)) == 0


async def test_no_zone_id_param_returns_all_zones_compared(client):
    with freeze_time('2020-01-14 14:00:00'):
        response = await client.get('/api/v0/predictions')
        response_data = await response.get_data()

    assert response.status_code == 200
    data = json.loads(response_data)
    assert len(data) > 0
    first_record = data[0]
    assert first_record['12monthPrediction']
    assert first_record['18monthPrediction']
    assert first_record['24monthPrediction']
    assert first_record['zoneId']


async def test_zone_ids_restricts_zones_compared(client):
    with freeze_time('2020-01-14 14:00:00'):
        response = await client.get('/api/v0/predictions?zone_ids=31004,31002')
        response_data = await response.get_data()

    assert response.status_code == 200
    data = json.loads(response_data)
    assert len(data) == 2


@contextmanager
def use_availability_provider(ap):
    og_ap = app.fybr_availability_provider
    app.fybr_availability_provider = ap
    yield
    app.fybr_availability_provider = og_ap


async def test_app_uses_availability_if_its_there(client):
    zone_with_availability_data = '31006'
    zone_without_availability_data = '31001'
    zone_we_did_not_ask_for = '31002'
    zone_ids = [zone_without_availability_data, zone_with_availability_data]

    uri='ws://localhost:5001/socket/websocket'
    meter_and_zone_list = [
        {'meter_id': '9861', 'zone_id': zone_with_availability_data},
        {'meter_id': '9862', 'zone_id': zone_with_availability_data},
        {'meter_id': '9863', 'zone_id': zone_with_availability_data},
        {'meter_id': '9864', 'zone_id': zone_with_availability_data},
        {'meter_id': '9865', 'zone_id': zone_we_did_not_ask_for}
    ]

    availability_provider = FybrAvailabilityProvider(uri, meter_and_zone_list)

    occupancy_messages = [
        update_event({'id': '9861', 'occupancy': 'UNOCCUPIED', 'time_of_ingest': '2020-05-21T18:00:00.000000'}),
        update_event({'id': '9862', 'occupancy': 'UNOCCUPIED', 'time_of_ingest': '2020-05-21T18:00:00.000000'}),
        update_event({'id': '9863', 'occupancy': 'OCCUPIED', 'time_of_ingest': '2020-05-21T18:00:00.000000'}),
        update_event({'id': '9864', 'occupancy': 'UNOCCUPIED', 'time_of_ingest': '2020-05-21T18:00:00.000000'}),
        update_event({'id': '9865', 'occupancy': 'UNOCCUPIED', 'time_of_ingest': '2020-05-21T18:00:00.000000'})
    ]
    fake_server = create_fake_server(messages=occupancy_messages)

    with use_availability_provider(availability_provider), \
        freeze_time('2020-05-21T18:05:00.000000'):          
        async with websockets.serve(fake_server, '127.0.0.1', 5001):
            await availability_provider.handle_websocket_messages()

        response = await client.get(f'/api/v1/predictions?zone_ids={",".join(zone_ids)}')
        response_data = await response.get_data()

    assert response.status_code == 200
    data = json.loads(response_data)
    assert data == [
        {
            'availabilityPrediction': 0.4312,
            'zoneId': zone_without_availability_data,
            'supplierID': '970010'
        },
        {
            'availabilityPrediction': 0.75,
            'zoneId': zone_with_availability_data,
            'supplierID': '970010'
        },
    ]