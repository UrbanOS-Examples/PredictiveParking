from abc import ABC
from abc import abstractmethod
from datetime import datetime
from itertools import starmap
from typing import List
from typing import Literal
from typing import Mapping
from typing import Union

import numpy as np
import pandas as pd
from pydantic import BaseModel
from pydantic import ValidationError
from pydantic import validate_arguments
from pydantic import validator
from sklearn.neural_network import MLPRegressor

from app import model_provider
from app import zone_info


class Predictor(ABC):
    """An abstract base class for trained predictive models"""
    @abstractmethod
    def predict(self, data):
        ...


class ParkingAvailabilityPredictorInput(BaseModel):
    timestamp: datetime = None
    zone_ids: Union[List[str], Literal['All']] = 'All'

    @validator('timestamp', pre=True, always=True)
    def use_current_time_if_no_timestamp_is_provided(cls, timestamp):
        return timestamp if timestamp is not None else datetime.now()

    @validator('zone_ids', pre=True, always=True)
    def all_zone_ids_are_valid(cls, zone_ids):
        known_parking_locations = zone_info.zone_ids()
        if zone_ids == 'All':
            zone_ids = known_parking_locations
        else:
            zone_ids = sorted(
                set(zone_ids).intersection(known_parking_locations),
                key=zone_ids.index
            )
        return list(zone_ids)


class ParkingAvailabilityPredictor(Predictor):
    def __init__(self, model_tag='latest'):
        super().__init__()
        self._location_models: Mapping[str, MLPRegressor] = model_provider.get_all(model_tag)

    @validate_arguments
    def predict(self, data: ParkingAvailabilityPredictorInput) -> Mapping[str, float]:
        if not during_hours_of_operation(data.timestamp):
            return {}

        model_inputs = extract_features(data.timestamp)

        cluster_ids = (zone_info.zone_cluster()
                                .assign(zoneID=lambda df: df.zoneID.astype(str))
                                .set_index('zoneID')
                                .loc[data.zone_ids, 'clusterID']
                                .map(str)
                                .tolist())

        return {
            zone_id: self._location_models[cluster_id]
                         .predict(np.asarray(model_inputs).reshape(1, -1))[0]
            for zone_id, cluster_id in zip(data.zone_ids, cluster_ids)
        }


def predict_with(models, input_datetime, zone_ids='All'):
    return pd.DataFrame(
        data={model: predict(input_datetime, zone_ids, model)
              for model in models}
    ).rename(
        columns=lambda model_tag: f'{model_tag}Prediction'
    ).assign(
        zoneId=ParkingAvailabilityPredictorInput(zone_ids=zone_ids).zone_ids
    ).to_dict('records')


def predict(input_datetime, zone_ids='All', model='latest'):
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
    _as_api_format : Defines the current prediction API format
    """
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
    dict of {str : float}
        A mapping of zone IDs to their predicted parking availability values.
        Parking availability is expressed as a ratio of available parking spots
        to total parking spots in each zone, represented as a float between 0
        and 1.
    """
    try:
        return ParkingAvailabilityPredictor(model_tag=model).predict({'timestamp': input_datetime, 'zone_ids': zone_ids})
    except ValidationError:
        return {}


def during_hours_of_operation(input_datetime):
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


def predict_as_api_format(predictions):
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
    predict_as_index : Predict parking availability given feature lists
    _as_api_format : Defines the current prediction API format
    """
    return list(starmap(_as_api_format, predictions.items()))


def _as_api_format(zone_id, predicted_val):
    return {
        'zoneId': zone_id,
        'availabilityPrediction': round(np.clip(predicted_val, 0, 1), 4),
        'supplierID': '970010'
    }