import pytest
import json
from freezegun import freeze_time

pytestmark = pytest.mark.asyncio


async def test_no_zone_id_param_returns_all_zones(client):
    with freeze_time("2020-01-14 14:00:00"):
        response = await client.get('/api/v1/predictions')
        data = await response.get_data()

    assert response.status_code == 200
    assert len(json.loads(data)) > 0


async def test_zone_ids_restricts_zones(client):
    with freeze_time("2020-01-14 14:00:00"):
        response = await client.get('/api/v1/predictions?zone_ids=31004,31002')
        data = await response.get_data()

    assert response.status_code == 200
    assert len(json.loads(data)) == 2

async def test_empty_zone_ids_returns_no_predictions(client):
    with freeze_time("2020-01-14 14:00:00"):
        response = await client.get('/api/v1/predictions?zone_ids=')
        data = await response.get_data()

    assert response.status_code == 200
    assert len(json.loads(data)) == 0

async def test_only_invalid_zone_ids_does_not_return_predictions(client):
    with freeze_time("2020-01-14 14:00:00"):
        response = await client.get('/api/v1/predictions?zone_ids=WQRQWEQ,ETWERWER,QWEQWRQ')
        data = await response.get_data()

    assert response.status_code == 200
    assert len(json.loads(data)) == 0

async def test_mixed_invalid_and_valid_zone_ids_returns_predictions_for_valid(client):
    with freeze_time("2020-01-14 14:00:00"):
        response = await client.get('/api/v1/predictions?zone_ids=WQRQWEQ,31004,QWEQWRQ')
        data = await response.get_data()

    assert response.status_code == 200
    assert len(json.loads(data)) == 1

async def test_time_out_of_hours_returns_no_predictions(client):
    with freeze_time("2020-01-14 05:00:00"):
        response = await client.get('/api/v1/predictions')
        data = await response.get_data()

    assert response.status_code == 200
    assert len(json.loads(data)) == 0

async def test_no_zone_id_param_returns_all_zones_compared(client):
    with freeze_time("2020-01-14 14:00:00"):
        response = await client.get('/api/v0/predictions')
        response_data = await response.get_data()

    assert response.status_code == 200
    data = json.loads(response_data)
    assert len(data) > 0
    first_record = data[0]
    assert first_record["12monthPrediction"]
    assert first_record["18monthPrediction"]
    assert first_record["24monthPrediction"]
    assert first_record["zoneId"]

async def test_zone_ids_restricts_zones_compared(client):
    with freeze_time("2020-01-14 14:00:00"):
        response = await client.get('/api/v0/predictions?zone_ids=31004,31002')
        response_data = await response.get_data()

    assert response.status_code == 200
    data = json.loads(response_data)
    assert len(data) == 2