from os import path
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
    # TODO - make this configurable from the environment or at least convention based
    bucket = s3.Bucket('dev-parking-prediction')

    models = {}
    base_model_file_path = mkdtemp()

    for cluster_id in cluster_ids:
        if not np.isnan(cluster_id):
            # TODO - make this load each into a ByteIO so we don't leave files strewn all over the FS
            # file_path = path.join(base_model_file_path, 'mlp_shortnorth_downtown_cluster' + str(int(cluster_id)))

            object_key = 'models/latest/mlp_shortnorth_downtown_cluster' + str(int(cluster_id))
            # bucket.download_file(object_key, file_path)
            print('downloading', object_key)
            with BytesIO() as bytesio:
                bucket.download_fileobj(object_key, bytesio)
                bytesio.seek(0)
                loaded_model = pickle.load(bytesio)
            # loaded_model = pickle.load(open(file_path, 'rb'))

            models[str(int(cluster_id))] = loaded_model

    return models