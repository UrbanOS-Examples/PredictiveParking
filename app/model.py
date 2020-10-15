"""
Responsible for defining the model backend for prediction requests, including
how those requests are converted into features that the current parking
availability predictor accepts.
"""
import logging
import sys
from abc import ABC
from abc import abstractmethod
from datetime import datetime
from typing import ForwardRef
from typing import List
from typing import Mapping
from typing import MutableMapping

import numpy as np
import pandas as pd
from fbprophet import Prophet
from pydantic import BaseModel
from pydantic import validate_arguments
from tqdm import tqdm

from app.data_formats import APIPrediction
from app.data_formats import APIPredictionRequest



from app._models.deep_hong import ModelFeaturesv0EarlyAccessPreRelease
from app._models.deep_hong import \
    ParkingAvailabilityModelv0EarlyAccessPreRelease

ModelFeatures = ModelFeaturesv0EarlyAccessPreRelease
ParkingAvailabilityModel = ParkingAvailabilityModelv0EarlyAccessPreRelease