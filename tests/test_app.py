import pytest
import json
from freezegun import freeze_time

def test_no_zone_id_param_returns_all_zones(client):
    with freeze_time("2020-01-14 14:00:00"):
        response = client.get('/api/v1/predictions')

    assert response.status_code == 200
    assert len(json.loads(response.data)) > 0

def test_zone_ids_restricts_zones(client):
    with freeze_time("2020-01-14 14:00:00"):
        response = client.get('/api/v1/predictions?zone_ids=31004,31002')

    assert response.status_code == 200
    assert len(json.loads(response.data)) == 2

def test_empty_zone_ids_returns_no_predictions(client):
    with freeze_time("2020-01-14 14:00:00"):
        response = client.get('/api/v1/predictions?zone_ids=')

    assert response.status_code == 200
    assert len(json.loads(response.data)) == 0

def test_only_invalid_zone_ids_does_not_return_predictions(client):
    with freeze_time("2020-01-14 14:00:00"):
        response = client.get('/api/v1/predictions?zone_ids=WQRQWEQ,ETWERWER,QWEQWRQ')

    assert response.status_code == 200
    assert len(json.loads(response.data)) == 0

def test_mixed_invalid_and_valid_zone_ids_returns_predictions_for_valid(client):
    with freeze_time("2020-01-14 14:00:00"):
        response = client.get('/api/v1/predictions?zone_ids=WQRQWEQ,31004,QWEQWRQ')

    assert response.status_code == 200
    assert len(json.loads(response.data)) == 1

def test_time_out_of_hours_returns_no_predictions(client):
    with freeze_time("2020-01-14 05:00:00"):
        response = client.get('/api/v1/predictions')

    assert response.status_code == 200
    assert len(json.loads(response.data)) == 0