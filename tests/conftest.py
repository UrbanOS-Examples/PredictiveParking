import asyncio
import functools
import itertools
import logging
import os
import pickle

import boto3
import pandas as pd
import pytest
import responses
from moto import mock_s3

from app import app
from app import keeper_of_the_state
from app.constants import DISCOVERY_API_QUERY_URL
from app.constants import MODEL_FILE_NAME
from app.keeper_of_the_state import MODELS_DIR_LATEST
from app.keeper_of_the_state import MODELS_DIR_ROOT
from app.model import ParkingAvailabilityModel

for noisy_logger_name in ['botocore', 'app.model']:
    logging.getLogger(noisy_logger_name).setLevel(logging.CRITICAL)


ALL_VALID_ZONE_IDS = [
    'twilight', 'auto', 'splash', 'danger', 'red', 'habitable', 'school',
    '-d out', 'spin', 'no spin', 'cal-', 'defense', 'end', 'residential',
    'commercial', 'industrial', '2', '3', '5', '7', '11', '13', '17', '19',
    '🦜', '🦜🦜', '🦜🦜🦜', '🦜🦜🦜🦜', '🦜🦜🦜🦜🦜', '🦜🦜🦜🦜🦜🦜', '🦜🦜🦜🦜🦜🦜🦜'
]


@pytest.yield_fixture(scope='function')
def event_loop(request):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='function')
def client(with_warmup):
    return app.test_client()


@pytest.fixture(scope='function')
def mocked_scos_zone_ids_query():
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            DISCOVERY_API_QUERY_URL,
            'zoneIds\n' + '\n'.join(ALL_VALID_ZONE_IDS)
        )
        yield rsps


@pytest.fixture(scope='function')
async def with_warmup(mocked_scos_zone_ids_query, fake_model_files_in_s3):
    await keeper_of_the_state.warm_caches()


@pytest.fixture(scope='session')
def all_valid_zone_ids():
    return ALL_VALID_ZONE_IDS


@pytest.fixture(scope='module')
def fake_dataset(all_valid_zone_ids):
    a_week_of_semihours = functools.reduce(
        lambda current_dates, new_dates: current_dates + new_dates.tolist(),
        [
            pd.date_range(
                start=f'2020-09-{day:0>2} 08:00',
                end=f'2020-09-{day:0>2} 22:00',
                freq='30min',
                closed='left'
            )
            for day in range(7, 13)
        ],
        []
    )

    return pd.DataFrame.from_records([
        {
            'zone_id': zone_id,
            'semihour': semihour,
            'occu_cnt_rate': occupancy_rate
        }
        for zone_id in all_valid_zone_ids
        for semihour, occupancy_rate in zip(
            a_week_of_semihours,
            itertools.repeat(0.2_3_5_7_11_13)
        )
    ])


@pytest.fixture(scope='module')
def fake_model(fake_dataset):
    model = ParkingAvailabilityModel()
    model.train(fake_dataset)
    return model


@pytest.fixture(scope='module')
def fake_model_files_in_s3(fake_model):
    os.environ['COMPARED_MODELS'] = '12month,18month,24month'
    with mock_s3():
        s3 = boto3.resource('s3')

        bucket = s3.Bucket('dev-parking-prediction')
        bucket.create()

        pickled_model = pickle.dumps(fake_model)
        pickled_model_s3_keys = [
            f'{MODELS_DIR_LATEST}/{MODEL_FILE_NAME}',
            f'{MODELS_DIR_ROOT}/12month/{MODEL_FILE_NAME}',
            f'{MODELS_DIR_ROOT}/18month/{MODEL_FILE_NAME}',
            f'{MODELS_DIR_ROOT}/24month/{MODEL_FILE_NAME}'
        ]

        for pickled_model_key in pickled_model_s3_keys:
            bucket.put_object(Body=pickled_model, Key=pickled_model_key)

        yield
