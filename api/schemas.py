from lib2to3.pytree import Base
from pydantic import BaseModel
from ocpp.v201 import enums
import datatypes

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class DB_Tables(str, Enum):

    Modem = "Modem"
    Charge_Point="Charge_Point"
    EVSE="EVSE"
    Connector="Connector"
    MeterValue="MeterValue"
    SignedMeterValue="SignedMeterValue"
    SampledValue="SampledValue"
    IdToken="IdToken"
    GroupIdToken="GroupIdToken"
    IdTokenInfo="IdTokenInfo"
    Transaction="Transaction"
    Transaction_Event="Transaction_Event"
    ChargingProfile="ChargingProfile"
    ChargingSchedule="ChargingSchedule"
    EventData="EventData"


@dataclass
class Get_from_table_Payload:
    table: DB_Tables
    filters: Optional[dict]

