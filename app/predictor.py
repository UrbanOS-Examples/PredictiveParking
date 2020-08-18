from itertools import starmap

import numpy as np

from app import model_provider
from app import zone_info


def predict_with(models, input_datetime, zone_ids='All'):
    predictions = {}
    lead_model = models[0]
    for model in models:
        predictions[model] = predict(input_datetime, zone_ids, model)

    zipped_predictions = []
    for index in range(len(predictions[lead_model])):
        zone_id = predictions[lead_model][index]['zoneId']
        zipped_prediction = {
            'zoneId': zone_id
        }

        for model in models:
            assert zone_id == predictions[model][index]['zoneId']
            zipped_prediction[f'{model}Prediction'] = predictions[model][index]['availabilityPrediction']

        zipped_predictions.append(zipped_prediction)
    return zipped_predictions


def predict(input_datetime, zone_ids='All', model='latest'):  
    index = predict_as_index(input_datetime, zone_ids, model)

    return predict_as_api_format(index)


def predict_as_index(input_datetime, zone_ids='All', model='latest'):
    """
    Predict the availability of parking in all parking zones at a given time.

    Parameters
    ----------
    input_datetime : datetime.datetime
        The date and time at which parking meter availability should be
        predicted.
    zone_ids : str or collection of hashable, optional
        The parking zones where availability estimates are being requested. The
        default is 'All', which will result in availability predictions for all
        parking zones.
    model : str, optional
        The identifier of the model parameters to use (default: 'latest').

    Returns
    -------
    dict
        A mapping of zone IDs to their predicted parking availability values.
        Parking availability is expressed as a ratio of available parking spots
        to total parking spots in each zone, represented as a float between 0
        and 1.
    """
    if not is_valid_input_datetime(input_datetime):
        return {}

    model_inputs = extract_features(input_datetime)
    models = model_provider.get_all(model)

    prediction_index = {}

    for _, row in zone_info.zone_cluster().iterrows():
        zone_id = str(row['zoneID'])
        if zone_ids != 'All' and zone_id not in zone_ids:
            continue

        cluster_id = row['clusterID']
        if not np.isnan(cluster_id):
            cluster_id = str(int(cluster_id))
            if cluster_id not in models:
                continue

            current_model = models[cluster_id]
            predicted_val = current_model.predict(np.asarray(model_inputs).reshape(1, -1))[0]

            prediction_index[zone_id] = predicted_val

    return prediction_index


def is_valid_input_datetime(input_datetime):
    return input_datetime.weekday() < 6 and 8 <= input_datetime.hour < 22


def extract_features(input_datetime):
    """
    Convert a given datetime to the input format expected by our parking
    availability models.

    Parameters
    ----------
    input_datetime : datetime.datetime
        The date and time from which to extract model inputs.

    Returns
    -------
    The concatenation of one-hot encoded time of day and day of the week values
    corresponding to `input_datetime`. Time of day values distributed into
    30-minute interval bins throughout the hours of parking meter operation.
    """
    semihour_index = 2 * (input_datetime.hour - 8) + input_datetime.minute // 30
    semihour_input = [0] * 28
    semihour_input[semihour_index] = 1

    day_index = input_datetime.weekday()
    day_input = [0] * 6
    day_input[day_index] = 1

    return semihour_input[1:] + day_input[1:]


def predict_as_api_format(index):
    return list(starmap(_as_api_format, index.items()))


def _as_api_format(zone_id, predicted_val):
    return {
        'zoneId': zone_id,
        'availabilityPrediction': round(np.clip(predicted_val, 0, 1), 4),
        'supplierID': '970010'
    }