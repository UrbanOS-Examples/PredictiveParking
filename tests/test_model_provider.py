import pickle

import boto3
import pytest
from freezegun import freeze_time
from mockito import kwargs
from mockito import when
from moto import mock_s3

from app import model_provider


@pytest.fixture(scope='module')
def setup_all():
    with mock_s3():
        conn = boto3.resource('s3')
        bucket = conn.Bucket('dev-parking-prediction')
        bucket.create()

        yield conn, bucket


@pytest.mark.asyncio
async def test_warm_is_resilient(fake_model_files_in_s3):
    actual_boto3_session = boto3.Session()
    with when(boto3).Session(**kwargs).thenRaise(Exception('this should not crash things')).thenReturn(actual_boto3_session):
        await model_provider.warm_model_caches()


def test_train_writes_models_to_s3(setup_all):
    conn, bucket = setup_all

    models = {
        '1': 'model 1',
        '2': 'model 2'
    }

    with freeze_time('2020-01-14 14:00:00'):
        model_provider.put_all(models)
    
    latest_content = list(bucket.objects.filter(Prefix='models/latest/'))
    dated_content = list(bucket.objects.filter(Prefix='models/historical/2020-01/2020-01-14/'))

    assert len(latest_content) == 2
    assert len(dated_content) == 2


def test_read_and_update_model(setup_all):
    _, bucket = setup_all

    models = {
        '1': 'model 1',
        '2': 'model 2'
    }

    with freeze_time('2020-01-14 14:00:00'):
        model_provider.put_all(models)

    assert get_latest_model() == 'model 1'

    models = {
        '1': 'updated model 1'
    }

    with freeze_time('2020-01-15 14:00:00'):
        model_provider.put_all(models)

    assert get_latest_model() == 'updated model 1'
    assert 1 == len(list(bucket.objects.filter(Prefix='models/latest/')))


def get_latest_model():
    conn = boto3.resource('s3')
    bucket = conn.Bucket('dev-parking-prediction')
    
    latest_content = list(bucket.objects.filter(Prefix='models/latest/'))

    object = conn.Object('dev-parking-prediction', latest_content[0].key)

    latest_model = pickle.loads(object.get()['Body'].read())

    return latest_model