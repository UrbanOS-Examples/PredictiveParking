import pytest

from app import app

from os import path, walk
from moto import mock_s3
import boto3
import pandas as pd


@pytest.fixture
def client(fake_model_files_in_s3):
    print('in fake app creator')
    with app.test_client() as client:
        yield client


@pytest.fixture(scope='module', autouse=True)
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

        yield