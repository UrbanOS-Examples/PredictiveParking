import boto3
import pickle

from os import path, environ
from datetime import date
from cachetools import cached, TTLCache
from io import BytesIO

from app import auth_provider

TTL_HOURS = 12
TTL_SECONDS = TTL_HOURS * 60 * 60

VAULT_ROLE = environ.get('VAULT_ROLE', '')
VAULT_CREDENTIALS_KEY = environ.get('VAULT_CREDENTIAL_KEY', '')
MODEL_FILE_PREFIX = 'mlp_shortnorth_downtown_cluster'
MODEL_LATEST_PATH = 'models/latest/'


def list_key(*args, **kwargs):
    return tuple(*args)


@cached(cache=TTLCache(maxsize=128, ttl=TTL_SECONDS), key=list_key)
def get_all(cluster_ids):
    bucket = _bucket_for_environment()
    models = {}

    for cluster_id in cluster_ids:
        cluster_id_string = str(cluster_id)
        model_path = MODEL_LATEST_PATH + MODEL_FILE_PREFIX + cluster_id_string

        with BytesIO() as in_memory_file:
            bucket.download_fileobj(model_path, in_memory_file)
            in_memory_file.seek(0)
            loaded_model = pickle.load(in_memory_file)

        models[cluster_id_string] = loaded_model

    return models


def put_all(models):
    bucket = _bucket_for_environment()

    dated_path = 'models/' + date.today().isoformat() + '/'

    for (cluster_id, model) in models.items():
        model_serialized = pickle.dumps(model)
        model_path = '/' + MODEL_FILE_PREFIX + cluster_id

        bucket.put_object(Body=model_serialized, Key=MODEL_LATEST_PATH + model_path)
        bucket.put_object(Body=model_serialized, Key=dated_path + model_path)    


def _bucket_for_environment():
    credentials = auth_provider.get_credentials(
        vault_role=VAULT_ROLE,
        vault_credentials_key=VAULT_CREDENTIALS_KEY
    )
    session = boto3.Session(**credentials)
    s3 = session.resource('s3')

    environment = environ.get('SCOS_ENV', 'dev')
    return s3.Bucket(environment + '-parking-prediction')