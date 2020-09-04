import datetime as dt
import warnings
from collections import defaultdict
from typing import Iterable
from unittest.mock import patch

import hypothesis.strategies as st
import numpy as np
from hypothesis import given
from sklearn.neural_network import MLPRegressor

from app import zone_info
from app.constants import DAY_OF_WEEK
from app.constants import HOURS_END
from app.constants import HOURS_START
from app.constants import TIME_ZONE
from app.constants import UNENFORCED_DAYS
from app.data_formats import APIPredictionRequest
from app.model import ParkingAvailabilityPredictor
from app.predictor import ModelFeatures


DATETIME_DURING_HOURS_OF_OPERATION = st.builds(
    dt.datetime.combine,
    date=st.dates().filter(lambda dt: DAY_OF_WEEK(dt.weekday()) not in UNENFORCED_DAYS),
    time=st.times(HOURS_START, HOURS_END),
    tzinfo=st.sampled_from([TIME_ZONE, None])
)

VALID_ZONE_IDS = st.lists(
    st.sampled_from(zone_info.zone_ids()),
    min_size=1,
    max_size=20
)


@given(
    timestamp=DATETIME_DURING_HOURS_OF_OPERATION,
    zone_ids=VALID_ZONE_IDS
)
def test_ModelFeatures_can_be_derived_from_prediction_APIPredictionRequest_during_hours_of_operation(timestamp, zone_ids):
    prediction_request = APIPredictionRequest(timestamp=timestamp, zone_ids=zone_ids)
    samples_batch = ModelFeatures.from_request(prediction_request)
    assert isinstance(samples_batch, Iterable)
    assert all(isinstance(sample, ModelFeatures) for sample in samples_batch)


@patch('app.model.model_provider')
@given(
    timestamp=DATETIME_DURING_HOURS_OF_OPERATION,
    zone_ids=VALID_ZONE_IDS
)
def test_ParkingAvailabilityPredictor_returns_one_prediction_per_valid_zone_id(model_provider, timestamp, zone_ids):
    prediction_request = APIPredictionRequest(timestamp=timestamp, zone_ids=zone_ids)
    samples_batch = ModelFeatures.from_request(prediction_request)
    sample = samples_batch[0]

    number_of_features = len(sample.dayofweek_onehot) + len(sample.semihour_onehot)
    common_model = MLPRegressor((1,), max_iter=1, tol=1e100)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        common_model.fit(np.random.rand(1, number_of_features), np.random.rand(1))
    stored_models = defaultdict(lambda: common_model)
    model_provider.get_all.return_value = stored_models

    predictor = ParkingAvailabilityPredictor()
    model_provider.get_all.assert_called()
    predictions = predictor.predict(samples_batch)
    assert set(predictions.keys()) == set(zone_ids)