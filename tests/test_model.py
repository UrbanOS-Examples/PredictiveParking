import datetime as dt
import pickle
from typing import Iterable

import hypothesis
import hypothesis.strategies as st
import joblib
from hypothesis import given

from app.constants import DAY_OF_WEEK
from app.constants import HOURS_END
from app.constants import HOURS_START
from app.constants import TIME_ZONE
from app.constants import UNENFORCED_DAYS
from app.data_formats import APIPredictionRequest
from app.model import ModelFeatures
from tests.conftest import ALL_VALID_ZONE_IDS

DATETIME_DURING_HOURS_OF_OPERATION = st.builds(
    dt.datetime.combine,
    date=st.dates(
        min_value=dt.date(2020, 9, 7),
        max_value=dt.date(2020, 9, 19)
    ).filter(
        lambda dt: DAY_OF_WEEK(dt.weekday()) not in UNENFORCED_DAYS
    ),
    time=st.times(HOURS_START, HOURS_END),
    tzinfo=st.sampled_from([TIME_ZONE, None])
)

VALID_ZONE_IDS = st.lists(
    st.sampled_from(ALL_VALID_ZONE_IDS),
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


@hypothesis.settings(deadline=1000000)
@given(
    timestamp=DATETIME_DURING_HOURS_OF_OPERATION,
    zone_ids=VALID_ZONE_IDS
)
def test_ParkingAvailabilityModel_returns_one_prediction_per_valid_zone_id(timestamp, zone_ids, fake_model, with_warmup):
    prediction_request = APIPredictionRequest(timestamp=timestamp, zone_ids=zone_ids)
    samples_batch = ModelFeatures.from_request(prediction_request)

    predictions = fake_model.predict(samples_batch)
    assert set(predictions.keys()) == set(zone_ids)


def test_ParkingAvailabilityModel_is_picklable(fake_model):
    pickle.dumps(fake_model)


def test_ParkingAvailabilityModel_unpickles_into_the_same_model(fake_model):
    pickled_fake_model = pickle.dumps(fake_model)
    unpickled_pickled_fake_model = pickle.loads(pickled_fake_model)
    assert joblib.hash(unpickled_pickled_fake_model) == joblib.hash(fake_model)