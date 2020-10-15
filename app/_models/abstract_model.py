from abc import ABC
from abc import abstractmethod
from typing import ForwardRef
from typing import List

import pandas as pd

from data_formats import APIPrediction


ModelFeatures = ForwardRef('ModelFeatures')


class Model(ABC):
    """An abstract base class for ML models."""

    @abstractmethod
    def __getstate__(self): ...

    @abstractmethod
    def __setstate__(self, state): ...

    @property
    @abstractmethod
    def supported_zones(self): ...

    @abstractmethod
    def train(self, training_data: pd.DataFrame) -> None: ...

    @abstractmethod
    def predict(self, data: ModelFeatures) -> List[APIPrediction]: ...