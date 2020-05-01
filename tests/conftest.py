import pytest

from app import app
from tests import fake_vault
import hvac

from os import path, walk
from moto import mock_s3
import boto3
import pandas as pd

import logging

logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('s3transfer').setLevel(logging.WARNING)

@pytest.fixture
def client(fake_model_files_in_s3):
    print('in fake app creator')
    with app.test_client() as client:
        yield client


@pytest.fixture
def credentials_from_vault(monkeypatch):
    access_key_id_from_vault = 'my_first_access_key_id'
    secret_access_key_from_vault = 'my_first_secret_key_value'

    monkeypatch.setattr(hvac, 'Client', fake_vault.successful_hvac_client(access_key_id_from_vault, secret_access_key_from_vault))
    monkeypatch.setattr('builtins.open', fake_vault.successful_token_file)

    return {'aws_access_key_id': access_key_id_from_vault, 'aws_secret_access_key': secret_access_key_from_vault}


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