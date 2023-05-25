from dataclasses import dataclass
from ocpp.v201 import enums
from typing import Dict, List, Optional


@dataclass
class LoginToken:
    token: str


@dataclass
class User:
    id : int = None
    cust_id : int = None
    full_name : str = None
    email : str = None
    status : str = None
    permission_level : int = None

@dataclass
class IdToken:
    id_token : str = None
    type : enums.IdTokenType = None

@dataclass
class Transaction:
    active : bool = None
    cable_max_current : int = None
    initial_export: float = None
    cp_id : str = None
    final_export: float = None
    evse_id : int = None
    transaction_id: str = None
    initial_import: float = None
    charging_state: enums.ChargingStateType = None
    final_import: float = None
    time_spent_charging: int = None
    soc: float = None
    stopped_reason: enums.ReasonType = None
    power_export: float = None
    remote_start_id: int = None
    power_import: float = None

@dataclass
class Charge_Station:
    model: str = None
    cp_id: str = None
    serial_number: str = None
    city: str = None
    longitude: str = None
    ocpp_version: str = None
    vendor_name: str = None
    firmware_version: str = None
    latitude: str = None
    country: str = None
    is_online: bool = None

@dataclass
class ReserveNowPayload:
    status: str = None
    status_info: Optional[Dict] = None
    id : int = None
