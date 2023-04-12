from dataclasses import dataclass
from enum import Enum
from ocpp.v201 import enums

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

class Charger_Action(str, Enum):
    stop="stop"
    normal_charge="normal_charge"
    pause="pause"
    charge="charge"
    discharge="discharge"

class Update_type(str, Enum):
    full="full"
    add="add"
    delete="delete"

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


@dataclass
class new_IdToken:
    charging_priority : int = None
    language1 : str = None
    language2 : str = None
    valid : bool = True
    id_token: str = None
    type:enums.IdTokenType = enums.IdTokenType.local

