import boto3
import botocore
import logging
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
    # Add the two args together into a single array
    return tuple(args[0] + [args[1]])


@cached(cache=TTLCache(maxsize=128, ttl=TTL_SECONDS), key=list_key)
def get_all(cluster_ids, model):
    bucket = _bucket_for_environment()
    models = {}

    for cluster_id in cluster_ids:
        cluster_id_string = str(cluster_id)
        model_path = f"models/{model}" + MODEL_FILE_PREFIX + cluster_id_string

        if not _model_exists_at_path(bucket, model_path):
            continue

        with BytesIO() as in_memory_file:
            bucket.download_fileobj(model_path, in_memory_file)
            in_memory_file.seek(0)
            loaded_model = pickle.load(in_memory_file)

        models[cluster_id_string] = loaded_model

    return models


def put_all(models):
    bucket = _bucket_for_environment()

    dated_path = 'models/' + date.today().isoformat() + '/'

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
        s3 = _s3_resource()
        s3.Object(bucket.name, path).load()
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
    session = boto3.Session(**credentials)
    return session.resource('s3')


def _bucket_for_environment():
    s3 = _s3_resource()
    environment = environ.get('SCOS_ENV', 'dev')
    return s3.Bucket(environment + '-parking-prediction')