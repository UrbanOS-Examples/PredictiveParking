"""
Responsible for defining the model backend for prediction requests, including
how those requests are converted into features that the current parking
availability predictor accepts.
"""
from app._models.prophets import ParkingProphet
from app._models.prophets import ProphetableFeatures

ModelFeatures = ProphetableFeatures
ParkingAvailabilityModel = ParkingProphet