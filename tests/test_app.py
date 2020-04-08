import pytest
import json

def test_simple(client):
    response = client.get('/api/v1/predictions')

    assert response.status_code == 200
    assert len(response.data) > 0

def test_with_zone_ids(client):
    response = client.get('/api/v1/predictions?zones=31004,31002')

    assert response.status_code == 200
    assert len(json.loads(response.data)) == 2