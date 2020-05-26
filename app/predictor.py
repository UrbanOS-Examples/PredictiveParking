from os import path
from datetime import datetime
from itertools import starmap
import pandas as pd
import numpy as np
import pickle
import logging
logging.basicConfig(level=logging.WARNING)

from app import model_provider
from app import zone_info


def predict_with(models, input_datetime, zone_ids='All'):
    predictions = {}
    lead_model = models[0]
    for model in models:
        predictions[model] = predict(input_datetime, zone_ids, model)

    zipped_predictions = []
    for index in range(len(predictions[lead_model])):
        zone_id = predictions[lead_model][index]["zoneId"]
        zipped_prediction = {
            "zoneId": zone_id
        }

        for model in models:
            assert zone_id == predictions[model][index]["zoneId"]
            zipped_prediction[f"{model}Prediction"] = predictions[model][index]["availabilityPrediction"]

        zipped_predictions.append(zipped_prediction)
    return zipped_predictions

def predict(input_datetime, zone_ids='All', model='latest'):  
    index = predict_as_index(input_datetime, zone_ids, model)

    return predict_as_api_format(index)

def predict_as_api_format(index):
    return list(starmap(_as_api_format, index.items()))

def predict_as_index(input_datetime, zone_ids='All', model='latest'):
    if not is_valid_input_datetime(input_datetime): return {}

    model_inputs = transform_datetime(input_datetime)
    models = model_provider.get_all(model)

    prediction_index = {}

    for _idx, row in zone_info.zone_cluster().iterrows():
        zone_id = str(row['zoneID'])
        if zone_ids != 'All' and zone_id not in zone_ids: continue

        cluster_id = row['clusterID']
        if not np.isnan(cluster_id):
            cluster_id = str(int(cluster_id))
            if cluster_id not in models:
                continue

            current_model = models[cluster_id]
            predicted_val = current_model.predict( np.asarray(model_inputs).reshape(1,-1) )[0]

            prediction_index[zone_id] = predicted_val

    return prediction_index

def is_valid_input_datetime(input_datetime):
    return input_datetime.weekday() < 6 and input_datetime.hour >= 8 and input_datetime.hour < 22

def transform_datetime(input_datetime):
    hour_index = 2 * (input_datetime.hour - 8) + input_datetime.minute//30
    hour_input = [0]*28
    hour_input[hour_index] = 1

    day_index = input_datetime.weekday()
    day_input = [0] * 6
    day_input[day_index] = 1

    return(hour_input[1:] + day_input[1:])

def _as_api_format(zone_id, predicted_val):
  return {
    "zoneId": zone_id,
    "availabilityPrediction": round(clamp(predicted_val), 4)
  }

def clamp(n, minn = 0, maxn = 1):
    return max(min(maxn, n), minn)