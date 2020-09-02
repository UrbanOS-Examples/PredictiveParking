import asyncio
import logging
import os

import boto3
import pytest
from moto import mock_s3

from app import app
from app import model_provider
from app.model_provider import MODELS_DIR_LATEST
from app.model_provider import MODELS_DIR_ROOT

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
    os.environ['COMPARED_MODELS'] = '12month,18month,24month'
    with mock_s3():
        conn = boto3.resource('s3')

        bucket = conn.Bucket('dev-parking-prediction')
        bucket.create()

        base_dir = os.path.dirname(os.path.abspath(__file__))
        fixture_dir = os.path.join(base_dir, 'fixtures')

        for directory, _, filenames in os.walk(fixture_dir):
            for filename in filenames:
                file_path = os.path.join(directory, filename)
                bucket.upload_file(file_path, f'{MODELS_DIR_LATEST}/{filename}')
                bucket.upload_file(file_path, f'{MODELS_DIR_ROOT}/12month/{filename}')
                bucket.upload_file(file_path, f'{MODELS_DIR_ROOT}/18month/{filename}')
                bucket.upload_file(file_path, f'{MODELS_DIR_ROOT}/24month/{filename}')

        yield