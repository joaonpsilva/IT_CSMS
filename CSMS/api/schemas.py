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
    EventData="EventData"


class Operation(str, Enum):
    SELECT="select"
    CREATE="create"
    REMOVE="remove"
    UPDATE="update"

@dataclass
class CRUD_Payload:
    operation: Operation
    table: DB_Tables
    filters: dict
    values: dict




####################################


class Transaction_Schema(BaseModel):
    transaction_id : Optional[str]
    charging_state : Optional[enums.ChargingStateType]
    time_spent_charging : Optional[int]
    stopped_reason : Optional[enums.ReasonType]
    remote_start_id : Optional[int]

