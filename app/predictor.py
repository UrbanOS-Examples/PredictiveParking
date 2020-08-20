import pandas as pd
from pydantic import ValidationError

from app.data_formats import PredictionAPIFormat
from app.data_formats import PredictionRequestAPIFormat
from app.model import ModelFeatures
from app.model import ParkingAvailabilityPredictor


def predict(input_datetime, zone_ids='All', model_tag='latest'):
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
    model_tag : str, optional
        The identifier of the model parameters to use (default: 'latest').

    Returns
    -------
    dict of {str : float}
        A mapping of zone IDs to their predicted parking availability values.
        Parking availability is expressed as a ratio of available parking spots
        to total parking spots in each zone, represented as a float between 0
        and 1.
    """
    if not during_hours_of_operation(input_datetime):
        predictions = {}
    else:
        try:
            predictions = ParkingAvailabilityPredictor(model_tag).predict(
                ModelFeatures.from_request(
                    PredictionRequestAPIFormat(
                        timestamp=input_datetime,
                        zone_ids=zone_ids
                    )
                )
            )
        except ValidationError as e:
            predictions = {}
    return predictions


def during_hours_of_operation(input_datetime):
    return input_datetime.weekday() < 6 and 8 <= input_datetime.hour < 22


def predict_with(models, input_datetime, zone_ids='All'):
    return pd.DataFrame(
        data={model: predict_formatted(input_datetime, zone_ids, model)
              for model in models}
    ).rename(
        columns=lambda model_tag: f'{model_tag}Prediction'
    ).assign(
        zoneId=PredictionRequestAPIFormat(zone_ids=zone_ids).zone_ids
    ).to_dict('records')


def predict_formatted(input_datetime, zone_ids='All', model='latest'):
    """
    Predict the availability of parking in a list of parking zones at a given
    time, returning a list of predictions in the current prediction API format.

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
    list of dict of {str : str or float}
        The predictions for each of the `zone_ids` converted to the current
        prediction API format.

    See Also
    --------
    PredictionAPIFormat : Defines the current prediction API record format
    """
    return to_api_format(predict(input_datetime, zone_ids, model))


def to_api_format(predictions):
    """
    Transform a dictionary of predictions into a list of outputs in API format.

    Parameters
    ----------
    predictions : dict of {str : float}
        A dictionary of `parking zone id -> availability prediction` pairs.

    Returns
    -------
    list of dict of {str : str or float}
        The predictions in `indexed_predictions` converted to the current
        prediction API format.

    See Also
    --------
    predict : Predict parking availability given feature lists
    PredictionAPIFormat : Defines the current prediction API record format
    """
    return [
        PredictionAPIFormat(
            zoneId=zone_id,
            availabilityPrediction=availability
        ).dict()
        for zone_id, availability in predictions.items()
    ]