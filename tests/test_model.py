import datetime as dt

import hypothesis.strategies as st
from hypothesis import given

from app.constants import DAY_OF_WEEK
from app.constants import HOURS_END
from app.constants import HOURS_START
from app.constants import TIME_ZONE
from app.constants import UNENFORCED_DAYS
from app.data_formats import APIPredictionRequest
from app.predictor import ModelFeatures


@given(
    timestamp=st.builds(
        dt.datetime.combine,
        date=st.dates().filter(lambda dt: DAY_OF_WEEK(dt.weekday()) not in UNENFORCED_DAYS),
        time=st.times(HOURS_START, HOURS_END),
        tzinfo=st.one_of(st.just(TIME_ZONE), st.none())
    ),
    zone_ids=st.lists(
        elements=st.from_regex(r'.+'),
        min_size=0,
        max_size=20,
        unique=True
    )
)
def test_ModelFeatures_can_be_derived_from_prediction_APIPredictionRequest_during_hours_of_operation(timestamp, zone_ids):
    prediction_request = APIPredictionRequest(timestamp=timestamp, zone_ids=zone_ids)
    assert isinstance(ModelFeatures.from_request(prediction_request), ModelFeatures)