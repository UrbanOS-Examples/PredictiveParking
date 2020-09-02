from datetime import datetime
from typing import List
from typing import Literal

from pydantic import BaseModel
from pydantic import confloat
from pydantic import constr
from pydantic import validator

from app import zone_info
from app.constants import PARK_MOBILE_SUPPLIER_ID


class APIPredictionRequest(BaseModel):
    timestamp: datetime = None
    zone_ids: List[str] = 'All'

    @validator('timestamp', pre=True, always=True)
    def use_current_time_if_no_timestamp_is_provided(cls, timestamp):
        return timestamp if timestamp is not None else datetime.now()

    @validator('zone_ids', pre=True, always=True)
    def all_zone_ids_are_valid(cls, zone_ids):
        known_parking_locations = zone_info.zone_ids()
        if zone_ids == 'All':
            zone_ids = known_parking_locations
        else:
            zone_ids = sorted(
                set(zone_ids).intersection(known_parking_locations),
                key=zone_ids.index
            )
        return list(zone_ids)


class APIPrediction(BaseModel):
    zoneId: constr(min_length=1)
    availabilityPrediction: confloat(ge=0, le=1)
    supplierID: Literal[PARK_MOBILE_SUPPLIER_ID] = PARK_MOBILE_SUPPLIER_ID

    @validator('availabilityPrediction', pre=True)
    def prediction_should_be_rounded(cls, availability_prediction):
        return round(availability_prediction, 4)