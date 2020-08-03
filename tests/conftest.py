import asyncio
import logging
from os import environ
from os import path
from os import walk

import boto3
import pytest
from moto import mock_s3

from app import app
from app import model_provider

logging.getLogger('botocore').setLevel(logging.WARN)


@pytest.yield_fixture(scope='session')
def event_loop(request):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='module')
def client(with_warmup):
    return app.test_client()


@pytest.fixture(scope='session')
async def with_warmup(fake_model_files_in_s3):
    logging.info('started warming model cache')
    await model_provider.warm_model_caches()
    logging.info('finished warming model cache')


@pytest.fixture(scope='session')
def fake_model_files_in_s3():
    environ['COMPARED_MODELS'] = '12month,18month,24month'
    with mock_s3():
        conn = boto3.resource('s3')

        bucket = conn.Bucket('dev-parking-prediction')
        bucket.create()

        base_dir = path.dirname(path.abspath(__file__))
        fixture_dir = path.join(base_dir, 'fixtures')

        for directory, _, filenames in walk(fixture_dir):
            for filename in filenames:
                file_path = path.join(directory, filename)
                bucket.upload_file(file_path, f'/models/latest/{filename}')
                bucket.upload_file(file_path, f'/models/12month/{filename}')
                bucket.upload_file(file_path, f'/models/18month/{filename}')
                bucket.upload_file(file_path, f'/models/24month/{filename}')

        yield