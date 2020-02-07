from app import predictor
from datetime import datetime

import pytest

def test_predict_returns_availablity_for_zones_during_normal_hours():
    predictions = predictor.predict(datetime(2020, 2, 8, 13, 29, 0))

    assert predictions
    for prediction in predictions:
        assert 'zoneId' in prediction
        assert 'availabilityPrediction' in prediction

def test_predict_returns_no_predictions_after_hours():
    predictions = predictor.predict(datetime(2020, 2, 6, 22, 0, 0))

    assert len(predictions) == 0

def test_predict_returns_no_predictions_on_sundays():
    predictions = predictor.predict(datetime(2020, 2, 9, 12, 0, 0))

    assert len(predictions) == 0