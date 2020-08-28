"""
Responsible for defining a model backend for prediction requests, including how
that model takes
"""
from abc import ABC
from abc import abstractmethod
from typing import List
from typing import Mapping

import numpy as np
from pydantic import BaseModel
from pydantic import conlist
from pydantic import validate_arguments
from pydantic import validator
from sklearn.neural_network import MLPRegressor

from app import model_provider
from app import zone_info
from app.data_formats import APIPrediction
from app.data_formats import APIPredictionRequest


class Predictor(ABC):
    """An abstract base class for trained predictive models"""
    @abstractmethod
    def predict(self, data: 'ModelFeatures') -> List[APIPrediction]:
        ...


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
    def from_request(request: APIPredictionRequest):
        """
        Convert a prediction request to the input format expected by a parking
        availability model.

        Parameters
        ----------
        request : APIPredictionRequest
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