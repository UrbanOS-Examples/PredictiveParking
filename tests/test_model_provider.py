from app import model_provider
import pytest
import boto3
import pickle
from moto import mock_s3
from freezegun import freeze_time


@pytest.fixture(scope='module')
def setup_all():
    with mock_s3():
        conn = boto3.resource('s3')
        bucket = conn.Bucket('dev-parking-prediction')
        bucket.create()

        yield conn, bucket


def test_train_writes_models_to_s3(setup_all):
    conn, bucket = setup_all

    models = {
        '1': 'model 1',
        '2': 'model 2'
    }

    with freeze_time("2020-01-14 14:00:00"):
        model_provider.put_all(models)
    
    latest_content = list(bucket.objects.filter(Prefix="models/latest/"))
    dated_content = list(bucket.objects.filter(Prefix="models/2020-01-14/"))

    assert len(latest_content) == 2
    assert len(dated_content) == 2


def test_read_and_update_model(setup_all):
    _, bucket = setup_all

    models = {
        '1': 'model 1',
        '2': 'model 2'
    }

    with freeze_time("2020-01-14 14:00:00"):
        model_provider.put_all(models)

    assert get_latest_model() == 'model 1'

    models = {
        '1': 'updated model 1'
    }

    with freeze_time("2020-01-15 14:00:00"):
        model_provider.put_all(models)

    assert get_latest_model() == 'updated model 1'
    assert 1 == len(list(bucket.objects.filter(Prefix="models/latest/")))


def get_latest_model():
    conn = boto3.resource('s3')
    bucket = conn.Bucket('dev-parking-prediction')
    
    latest_content = list(bucket.objects.filter(Prefix="models/latest/"))

    object = conn.Object('dev-parking-prediction', latest_content[0].key)

    latest_model = pickle.loads(object.get()['Body'].read())

    return latest_model