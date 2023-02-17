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
    mode : dict

