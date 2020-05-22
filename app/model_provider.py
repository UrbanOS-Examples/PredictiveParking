import boto3
import botocore
import logging
import pickle

from os import path, environ, getenv
from datetime import date
from cachetools import cached, TTLCache
from io import BytesIO
import pandas as pd
import asyncio
from itertools import starmap

from app import auth_provider
from app import zone_info

TTL_HOURS = 12
TTL_SECONDS = TTL_HOURS * 60 * 60

VAULT_ROLE = environ.get('VAULT_ROLE', '')
VAULT_CREDENTIALS_KEY = environ.get('VAULT_CREDENTIALS_KEY', '')
MODEL_FILE_PREFIX = 'mlp_shortnorth_downtown_cluster'
MODEL_LATEST_PATH = 'models/latest/'

MODELS = {}

def get_all(model='latest'):
    return MODELS.get(model, {})
    

def warm_model_caches_synchronously():
    print('getting models for prediction')
    asyncio.get_event_loop().run_until_complete(warm_model_caches())
    print('done getting models for prediction')

async def warm_model_caches():
    models = get_comparative_models()
    model_fetches = [_fetch_all('latest')]

    for model in models:
        model_fetches.append(_fetch_all(model))

    fetched_models = await asyncio.gather(*model_fetches)

    for (name, model_dict) in fetched_models:
        MODELS[name] = model_dict


async def fetch_models_periodically():
    while True:
        await asyncio.sleep(TTL_SECONDS)
        await warm_model_caches()


def _fetch_model(id, bucket, model_path):
    logging.debug(f"fetching: {model_path}")
    with BytesIO() as in_memory_file:
        bucket.download_fileobj(model_path, in_memory_file)
        in_memory_file.seek(0)
        logging.debug(f"done fetching {model_path}")
        return (id, pickle.load(in_memory_file))


async def _fetch_all(time_span):
    bucket = await asyncio.get_event_loop().run_in_executor(None, _bucket_for_environment)

    def _as_path(cluster_id):
        cluster_id_string = str(cluster_id)
        return (cluster_id_string, f"models/{time_span}/" + MODEL_FILE_PREFIX + cluster_id_string)

    async def _check_exists(id, path):
        return (id, path, await asyncio.get_event_loop().run_in_executor(None, _model_exists_at_path, bucket, path))

    def _filter_exists(path_tuple):
        _id, _path, exists = path_tuple
        return exists

    async def _model_download(id, path, _exists):
        return await asyncio.get_event_loop().run_in_executor(None, _fetch_model, id, bucket, path)

    model_paths = map(_as_path, zone_info.cluster_ids())

    model_exists_futures = list(starmap(_check_exists, model_paths))
    model_exists = await asyncio.gather(*model_exists_futures)
    existing_model_paths = filter(_filter_exists, model_exists)

    model_futures = list(starmap(_model_download, existing_model_paths))
    models = await asyncio.gather(*model_futures)

    return (time_span, dict(models))


def put_all(models):
    bucket = _bucket_for_environment()

    dated_path = 'models/historical/' + date.today().strftime("%Y-%m") + '/' + date.today().isoformat() + '/'

    _delete_models_in_path(bucket, dated_path)
    _delete_models_in_path(bucket, MODEL_LATEST_PATH)

    for (cluster_id, model) in models.items():
        model_serialized = pickle.dumps(model)
        model_path = MODEL_FILE_PREFIX + cluster_id

        logging.info(f"Loading {model_path} into {bucket.name}")

        bucket.put_object(Body=model_serialized, Key=MODEL_LATEST_PATH + model_path)
        bucket.put_object(Body=model_serialized, Key=dated_path + model_path)    


def _model_exists_at_path(bucket, path):
    try:
        logging.debug(f"checking if model exists at {path}")
        s3 = _s3_resource()
        s3.Object(bucket.name, path).load()
        logging.debug(f"done checking model exists at {path}")
        return True
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            return False
        else:
            raise e


def _delete_models_in_path(bucket, path):
    def _convert_to_delete_syntax(object_summary):
        return {'Key': object_summary.key}

    existing_models = bucket.objects.filter(Prefix=path)
    models_to_delete = list(map(_convert_to_delete_syntax, existing_models))

    if models_to_delete != []:
        bucket.delete_objects(Delete={'Objects': models_to_delete})


def _s3_resource():
    credentials = auth_provider.get_credentials(
        vault_role=VAULT_ROLE,
        vault_credentials_key=VAULT_CREDENTIALS_KEY
    )
    config = botocore.config.Config(
        max_pool_connections=50,
    )
    session = boto3.Session(**credentials)
    return session.resource('s3', config=config)


def _bucket_for_environment():
    s3 = _s3_resource()
    environment = environ.get('SCOS_ENV', 'dev')
    return s3.Bucket(environment + '-parking-prediction')

def get_comparative_models():
    return getenv('COMPARED_MODELS', '12month,18month,24month').split(',')