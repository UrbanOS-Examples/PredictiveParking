import pytest

from app import app
from app import model_provider

from os import path, walk
from moto import mock_s3
import boto3
import pandas as pd

import logging
logging.getLogger('botocore').setLevel(logging.WARN)


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
    with mock_s3():
        conn = boto3.resource('s3')

        bucket = conn.Bucket('dev-parking-prediction')
        bucket.create()

        base_dir = path.dirname(path.abspath(__file__))
        fixture_dir = path.join(base_dir, 'fixtures')

        for (directory, _, filenames) in walk(fixture_dir):
            for filename in filenames:
                file_path = path.join(directory, filename)
                bucket.upload_file(file_path, '/models/latest/' + filename)
                bucket.upload_file(file_path, '/models/1month/' + filename)
                bucket.upload_file(file_path, '/models/3month/' + filename)
                bucket.upload_file(file_path, '/models/6month/' + filename)

        yield