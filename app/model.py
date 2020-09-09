"""
Responsible for defining a model backend for prediction requests, including how
that model takes
"""
import logging
import sys
from abc import ABC
from abc import abstractmethod
from typing import ForwardRef
from typing import List
from typing import Mapping
from typing import MutableMapping

import numpy as np
import pandas as pd
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


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
if sys.stdout.isatty():
    LOGGER.addHandler(logging.StreamHandler(sys.stdout))


TOTAL_SEMIHOURS = 2 * (HOURS_END - HOURS_START).hours + abs(HOURS_END.minute - HOURS_START.minute) // 30
TOTAL_ENFORCEMENT_DAYS = 7 - len(UNENFORCED_DAYS)


ModelFeatures = ForwardRef('ModelFeatures')


class Model(ABC):
    """An abstract base class for ML models."""

    @abstractmethod
    def train(self, training_data: pd.DataFrame) -> None:
        ...

    @abstractmethod
    def predict(self, data: ModelFeatures) -> List[APIPrediction]:
        ...


class ModelFeatures(BaseModel):
    zone_id: str
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
        assert number_of_ones + number_of_zeros == len(feature), \
            'Input should consist solely of 0s and 1s.'
        assert number_of_ones <= 1, \
            'Input must contain at most one 1.'
        return feature

    @staticmethod
    @validate_arguments
    def from_request(request: APIPredictionRequest) -> List[ModelFeatures]:
        """
        Convert a prediction request to the input format expected by a parking
        availability model.

        Parameters
        ----------
        request : APIPredictionRequest
            The prediction request to transform into model features

        Returns
        -------
        list of ModelFeatures
            A set of features that can be passed into the `predict` method of a
            `ParkingAvailabilityModel`.
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

        return [ModelFeatures(zone_id=zone_id,
                              semihour_onehot=semihour_onehot.astype(int).tolist(),
                              dayofweek_onehot=dayofweek_onehot.astype(int).tolist())
                for zone_id in request.zone_ids]


ModelFeatures.update_forward_refs()


class ParkingAvailabilityModel(Model):
    def __init__(self):
        super().__init__()
        self._location_models: MutableMapping[str, MLPRegressor] = {}

    def train(self, training_data: pd.DataFrame) -> None:
        zone_id, X, y = (
            training_data
                .assign(
                    available_rate=lambda df: 1 - df.occu_cnt_rate,
                    dayofweek=lambda df: df.semihour.dt.dayofweek.astype('category'),
                    semihour=lambda df: pd.Series(
                        zip(df.semihour.dt.hour, df.semihour.dt.minute),
                        dtype='category', index=df.index))
                .pipe(
                    lambda df: (
                        df.zone_id,
                        pd.get_dummies(df.loc[:, ['semihour', 'dayofweek']],
                                       drop_first=True),
                        df.available_rate))
        )

        for zone in zone_id.unique():
            LOGGER.info(f'Processing zone {zone}')
            X_cluster = X[zone_id == zone]
            y_cluster = y[zone_id == zone]

            if X_cluster.empty:
                LOGGER.info(
                    f'No data available for zone {zone}, not creating model')
                continue

            LOGGER.info(f'Total (row, col) counts: {X_cluster.shape}')

            mlp = MLPRegressor(hidden_layer_sizes=(50, 50), activation='relu')
            mlp.fit(X_cluster, y_cluster)
            self._location_models[str(int(zone))] = mlp

        LOGGER.info(f'Successfully trained {len(self._location_models)} models')

    @validate_arguments
    def predict(self, samples_batch: List[ModelFeatures]) -> Mapping[str, float]:
        requested_zone_ids = [sample.zone_id for sample in samples_batch]
        cluster_ids = (zone_info.zone_cluster()
                                .assign(zoneID=lambda df: df.zoneID.astype(str))
                                .set_index('zoneID')
                                .loc[requested_zone_ids, 'clusterID']
                                .map(str)
                                .tolist())
        regressor_feature_array = np.asarray([
            sample.semihour_onehot + sample.dayofweek_onehot
            for sample in samples_batch
        ])
        return {
            zone_id: self._location_models[cluster_id]
                         .predict(regressor_feature_array)[0]
            for zone_id, cluster_id in zip(requested_zone_ids, cluster_ids)
        }

    @classmethod
    def from_artifact(cls, model_tag='latest'):
        predictor = cls()
        predictor._location_models = model_provider.get_all(model_tag)
        return predictor

    def to_artifact(self):
        return self._location_models