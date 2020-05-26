from app import predictor
from app import model_provider
from app import availability_provider

from datetime import datetime

import pytest
import logging


def test_predict_returns_availablity_for_zone_ids_during_normal_hours(with_warmup):
    predictions = predictor.predict(datetime(2020, 2, 8, 13, 29, 0))

    assert predictions
    for prediction in predictions:
        assert 'zoneId' in prediction
        assert 'availabilityPrediction' in prediction

def test_predict_returns_no_predictions_after_hours(with_warmup):
    predictions = predictor.predict(datetime(2020, 2, 6, 22, 0, 0))

    assert len(predictions) == 0

def test_predict_returns_no_predictions_on_sundays(with_warmup):
    predictions = predictor.predict(datetime(2020, 2, 9, 12, 0, 0))

    assert len(predictions) == 0

def test_predict_for_provided_zone_ids(with_warmup):
    zone_ids = ['31001', '31006']
    predictions = predictor.predict(datetime(2020, 2, 8, 13, 29, 0), zone_ids)

    assert predictions
    for prediction in predictions:
        assert prediction['zoneId'] in zone_ids
