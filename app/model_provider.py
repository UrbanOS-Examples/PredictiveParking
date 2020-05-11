from os import path
import os
import numpy as np
import pickle
from datetime import date
from cachetools import cached, TTLCache

import boto3
from tempfile import mkdtemp
from app import auth_provider

from io import BytesIO

ttl_hours = 12
ttl_seconds = ttl_hours * 60 * 60
ttl_cache = TTLCache(maxsize=128, ttl=ttl_seconds)


def list_key(*args, **kwargs):
    return tuple(*args)


@cached(cache=ttl_cache, key=list_key)
def get_all(cluster_ids):
    credentials = auth_provider.get_credentials()
    session = boto3.Session(**credentials)

    s3 = session.resource('s3')
    environment = os.getenv('SCOS_ENV') or 'dev'
    bucket = s3.Bucket(environment + '-parking-prediction')

    models = {}

    for cluster_id in cluster_ids:
        cluster_id_string = str(int(cluster_id))
        object_key = 'models/latest/mlp_shortnorth_downtown_cluster' + cluster_id_string
        with BytesIO() as bytesio:
            bucket.download_fileobj(object_key, bytesio)
            bytesio.seek(0)
            loaded_model = pickle.load(bytesio)

        models[cluster_id_string] = loaded_model

    return models

def put_all(models):
    credentials = auth_provider.get_credentials(
        vault_role='parking-prediction-train-role',
        vault_credentials_key='parking_prediction_train'
    )
    session = boto3.Session(**credentials)

    s3 = session.resource('s3')
    environment = os.getenv('SCOS_ENV') or 'dev'
    bucket = s3.Bucket(environment + '-parking-prediction')

    latest_obj_key = 'models/latest'
    dated_obj_key = 'models/' + date.today().isoformat()

    for (k, v) in models.items():
        model_object = pickle.dumps(v)
        bucket.put_object(Body=model_object, Key=latest_obj_key + '/mlp_shortnorth_downtown_cluster' + k)
        bucket.put_object(Body=model_object, Key=dated_obj_key + '/mlp_shortnorth_downtown_cluster' + k)    