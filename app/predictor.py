from os import path
from datetime import datetime
import pandas as pd
import numpy as np
import pickle
import logging
logging.basicConfig(level=logging.NOTSET)

from app import model_thingy

def predict(input_datetime, zone_ids='All'):
    if not is_valid_input_datetime(input_datetime): return []

    base_dir = path.dirname(path.abspath(__file__))

    model_inputs = transform_datetime(input_datetime)
    # read zone information
    # zone_centroid_cluster = pd.read_csv(path.join(base_dir, "meter_config/zone_centroid_cluster_short_north.csv"))
    zone_cluster = pd.read_csv(path.join(base_dir, "meter_config/zone_cluster16_short_north_downtown_15_19.csv"))

    cluster_ids = zone_cluster.clusterID.unique().tolist()

    models = model_thingy.get_all(cluster_ids)

    prediction_output = []

    for idx, row in zone_cluster.iterrows():
        zone_id = str(row['zoneID'])
        if zone_ids != 'All' and zone_id not in zone_ids: continue

        cluster_id = row['clusterID']
        if not np.isnan(cluster_id):
            cluster_id = str(int(cluster_id))
            current_model = models[cluster_id]
            predicted_val = current_model.predict( np.asarray(model_inputs).reshape(1,-1) )[0]
            prediction = {
                "zoneId": zone_id,
                "availabilityPrediction": round(clamp(predicted_val), 4)
            }

            prediction_output.append(prediction)

    return prediction_output

def is_valid_input_datetime(input_datetime):
    return input_datetime.weekday() < 6 and input_datetime.hour >= 8 and input_datetime.hour < 22

def transform_datetime(input_datetime):
    hour_index = 2 * (input_datetime.hour - 8) + input_datetime.minute//30
    hour_input = [0]*28
    hour_input[hour_index] = 1

    day_index = input_datetime.weekday()
    day_input = [0] * 6
    day_input[day_index] = 1

    month_index = input_datetime.month
    month_input = [0] * 12
    month_input[month_index-1] = 1

    return(hour_input[1:] + day_input[1:] + month_input[1:])

def clamp(n, minn = 0, maxn = 1):
    return max(min(maxn, n), minn)

