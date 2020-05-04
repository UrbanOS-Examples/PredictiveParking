from os import path
import os
import numpy as np
import pickle
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
    base_model_file_path = mkdtemp()

    for cluster_id in cluster_ids:
        if not np.isnan(cluster_id):
            object_key = 'models/latest/mlp_shortnorth_downtown_cluster' + str(int(cluster_id))
            with BytesIO() as bytesio:
                bucket.download_fileobj(object_key, bytesio)
                bytesio.seek(0)
                loaded_model = pickle.load(bytesio)

            models[str(int(cluster_id))] = loaded_model

    return models