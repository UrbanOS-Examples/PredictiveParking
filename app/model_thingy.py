from os import path
import numpy as np
import pickle
from cachetools import cached, TTLCache

from io import BytesIO
import boto3
from tempfile import mkdtemp

ttl_cache = TTLCache(maxsize=128, ttl=300)
def list_key(*args, **kwargs):
    return tuple(*args)


@cached(cache=ttl_cache, key=list_key)
def get_all(cluster_ids):
    print("In get_all")
    s3 = boto3.resource('s3')
    bucket = s3.Bucket('dev-parking-prediction')

    models = {}
    base_model_file_path = mkdtemp()

    for cluster_id in cluster_ids:
        if not np.isnan(cluster_id):
            file_path = path.join(base_model_file_path, 'mlp_shortnorth_downtown_cluster' + str(int(cluster_id)))

            object_key = 'models/latest/mlp_shortnorth_downtown_cluster' + str(int(cluster_id))
            bucket.download_file(object_key, file_path)
            loaded_model = pickle.load(open(file_path, 'rb'))

            models[str(int(cluster_id))] = loaded_model

    return models