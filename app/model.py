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
from app.constants import DAY_OF_WEEK
from app.constants import HOURS_END
from app.constants import HOURS_START
from app.constants import UNENFORCED_DAYS
from app.data_formats import APIPrediction
from app.data_formats import APIPredictionRequest


TOTAL_SEMIHOURS = 2 * (HOURS_END - HOURS_START).hours + abs(HOURS_END.minute - HOURS_START.minute) // 30
TOTAL_ENFORCEMENT_DAYS = 7 - len(UNENFORCED_DAYS)


class Predictor(ABC):
    """An abstract base class for trained predictive models"""
    @abstractmethod
    def predict(self, data: 'ModelFeatures') -> List[APIPrediction]:
        ...


class ModelFeatures(BaseModel):
    zone_ids: List[str]
    semihour_onehot: conlist(int,
                             min_items=TOTAL_SEMIHOURS - 1,
                             max_items=TOTAL_SEMIHOURS - 1)
    dayofweek_onehot: conlist(int,
                              min_items=TOTAL_ENFORCEMENT_DAYS - 1,
                              max_items=TOTAL_ENFORCEMENT_DAYS - 1)

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
        timestamp = request.timestamp

        semihour_onehot = TOTAL_SEMIHOURS * [0]
        semihour_index = min(
            2 * (timestamp.hour - HOURS_START.hour) + timestamp.minute // 30,
            len(semihour_onehot) - 1
        )
        semihour_onehot[semihour_index] = 1

        dayofweek_onehot = TOTAL_ENFORCEMENT_DAYS * [0]
        enforcement_day_index = -1
        dayofweek_to_index = {day.value: (enforcement_day_index := enforcement_day_index + 1)
                              for day in DAY_OF_WEEK if day not in UNENFORCED_DAYS}

        day_index = timestamp.weekday()
        dayofweek_onehot[dayofweek_to_index[day_index]] = 1

        return ModelFeatures(
            zone_ids=request.zone_ids,
            semihour_onehot=semihour_onehot[1:],
            dayofweek_onehot=dayofweek_onehot[1:]
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