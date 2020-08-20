from abc import ABC
from abc import abstractmethod
from datetime import datetime
from typing import List
from typing import Literal
from typing import Mapping
from typing import Union

import numpy as np
import pandas as pd
from pydantic import BaseModel
from pydantic import ValidationError
from pydantic import confloat
from pydantic import conlist
from pydantic import constr
from pydantic import validate_arguments
from pydantic import validator
from sklearn.neural_network import MLPRegressor

from app import model_provider
from app import zone_info


PARK_MOBILE_SUPPLIER_ID: str = '970010'


class Predictor(ABC):
    """An abstract base class for trained predictive models"""
    @abstractmethod
    def predict(self, data):
        ...


class PredictionRequestAPIFormat(BaseModel):
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


class PredictionAPIFormat(BaseModel):
    zoneId: constr(min_length=1)
    availabilityPrediction: confloat(ge=0, le=1)
    supplierID: Literal[PARK_MOBILE_SUPPLIER_ID] = PARK_MOBILE_SUPPLIER_ID

    @validator('availabilityPrediction', pre=True)
    def prediction_should_be_rounded(cls, availability_prediction):
        return round(availability_prediction, 4)


class ModelFeatures(BaseModel):
    zone_ids: List[str]
    semihour_onehot: conlist(int, min_items=27, max_items=27)
    dayofweek_onehot: conlist(int, min_items=5, max_items=5)

    @validator('semihour_onehot', 'dayofweek_onehot')
    def one_hot_encoded(cls, feature):
        number_of_ones = (np.array(feature) == 1).sum()
        number_of_zeros = (np.array(feature) == 0).sum()
        assert number_of_ones + number_of_zeros == len(feature)
        assert number_of_ones <= 1
        return feature

    @staticmethod
    @validate_arguments
    def from_request(request: PredictionRequestAPIFormat):
        """
        Convert a prediction request to the input format expected by a parking
        availability model.

        Parameters
        ----------
        request : PredictionRequestAPIFormat
            The prediction request to transform into model features

        Returns
        -------
        ModelFeatures
            A set of features that can be passed into the `predict` method of a
            `ParkingAvailabilityPredictor`.
        """
        input_datetime = request.timestamp
        semihour_index = 2 * (input_datetime.hour - 8) + input_datetime.minute // 30
        semihour_input = [0] * 28
        semihour_input[semihour_index] = 1

        day_index = input_datetime.weekday()
        day_input = [0] * 6
        day_input[day_index] = 1

        return ModelFeatures(
            zone_ids=request.zone_ids,
            semihour_onehot=semihour_input[1:],
            dayofweek_onehot=day_input[1:]
        )


class ParkingAvailabilityPredictor(Predictor):
    def __init__(self, model_tag='latest'):
        super().__init__()
        self._location_models: Mapping[str, MLPRegressor] = model_provider.get_all(model_tag)

    @validate_arguments
    def predict(self, features: ModelFeatures) -> Mapping[str, float]:
        cluster_ids = (zone_info.zone_cluster()
                                .assign(zoneID=lambda df: df.zoneID.astype(str))
                                .set_index('zoneID')
                                .loc[features.zone_ids, 'clusterID']
                                .map(str)
                                .tolist())
        regressor_feature_array = np.asarray(
            features.semihour_onehot + features.dayofweek_onehot
        ).reshape(1, -1)
        return {
            zone_id: self._location_models[cluster_id]
                         .predict(regressor_feature_array)[0]
            for zone_id, cluster_id in zip(features.zone_ids, cluster_ids)
        }


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