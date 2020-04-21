### this is to test the model
from datetime import datetime
import sys
import pandas as pd
import numpy as np
import pickle
import json
import os.path


def transform_datetime(year, month, day, hour, minutes):
    # year, month, day, hour, minutes must be ints
    try:
        input_datetime = datetime(year, month, day, hour, minutes )
    except ValueError as e:
        print(e)
        print("Use current datetime instead.")
        input_datetime = datetime.now()
    print("Predicting parking availability at", input_datetime)

    # hour = now.hour # must between 8:00 - 21:59
    if hour < 8 or hour > 21:
        print("Parking is free after 22:00. Enter time between 8:00 to 22:00.")
        sys.exit()
    hour_index = 2 * (input_datetime.hour - 8) + input_datetime.minute//30
    hour_input = [0]*28
    hour_input[hour_index] = 1
    
    # day = now.weekday() # must not be 6 
    day_index = input_datetime.weekday()
    if day_index > 5:
        print("Parking is free on Sundays!")
        sys.exit()
    day_input = [0] * 6
    day_input[day_index] = 1
    
    month_index = input_datetime.month
    month_input = [0] * 12
    month_input[month_index-1] = 1

    return(hour_input[1:] + day_input[1:] + month_input[1:])

def clamp(n, minn = 0, maxn = 1):
    return max(min(maxn, n), minn)

if __name__ == "__main__":
    if len(sys.argv) == 6:
        year = int(sys.argv[1])
        month = int(sys.argv[2])
        day = int(sys.argv[3])
        hour = int(sys.argv[4])
        minutes = int(sys.argv[5])
    else:
        if len(sys.argv) > 1:
            print("specify datetime like yyyy MM dd hh mm : 2020 02 15 10 30")
            sys.exit()
        else:
            now = datetime.now()
            year = now.year
            month = now.month
            day = now.weekday()
            hour = now.hour
            minutes = now.minute
        
    model_inputs = transform_datetime(year, month, day, hour, minutes)
    # read zone information
    zone_cluster = pd.read_csv("meter_config/zone_cluster16_short_north_downtown_15_19.csv")
    
    # load the model from disk
    model_path = "models"
    models = {}
    for cluster_id in zone_cluster.clusterID.unique():
        if not np.isnan(cluster_id):
            loaded_model = pickle.load(open(model_path + "/mlp_shortnorth_downtown_50_50_19_0414_cluster" + str(int(cluster_id)), 'rb'))
            models[str(int(cluster_id))] = loaded_model

    prediction_output = {}
    for idx, row in zone_cluster.iterrows():
        zone_id = str(row['zoneID'])
        cluster_id = row['clusterID']
        if not np.isnan(cluster_id):
            cluster_id = str(int(cluster_id))
            current_model = models[cluster_id]
            predicted_val = current_model.predict( np.asarray(model_inputs).reshape(1,-1) )[0]
            prediction_output[zone_id] = round(clamp(predicted_val), 4) # limit this availability to be between 0 and 1
    
    print(prediction_output)

    # write into json file
    with open(os.path.abspath("") + '/output/predicted_values_'+'_'.join([str(year), str(month), str(day), str(hour), str(minutes)]) + '.txt', 'w') as outfile:
        json.dump(prediction_output, outfile)
    