from dataclasses import dataclass
from ocpp.v201 import enums
from typing import Dict, List, Optional


@dataclass
class LoginToken:
    token: str


@dataclass
class User:
    id : int
    cust_id : int
    full_name : str
    email : str
    status : str
    permission_level : int

@dataclass
class IdToken:
    id_token : str
    type : enums.IdTokenType

@dataclass
class Transaction:
    active : bool
    cable_max_current : int
    initial_export: float
    cp_id : str
    final_export: float
    evse_id : int
    transaction_id: str
    initial_import: float
    charging_state: enums.ChargingStateType
    final_import: float
    time_spent_charging: int
    soc: float
    stopped_reason: enums.ReasonType
    power_export: float
    remote_start_id: int
    power_import: float

@dataclass
class Charge_Station:
    model: str
    cp_id: str
    serial_number: str
    city: str
    longitude: str
    ocpp_version: str
    vendor_name: str
    firmware_version: str
    latitude: str
    country: str
    is_online: bool

@dataclass
class ReserveNowPayload:
    status: str
    status_info: Optional[Dict] = None
    id : int = None
