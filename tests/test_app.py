import pytest

def test_simple(client):
    response = client.get('/api/v1/predictions')

    assert response.status_code == 200
    assert len(response.data) > 0