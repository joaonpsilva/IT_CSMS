from lib2to3.pytree import Base
from pydantic import BaseModel
from ocpp.v201 import call, call_result, enums
import datatypes

from typing import Dict, List, Optional
from dataclasses import dataclass



@dataclass
class RequestStartTransaction_Payload:
    id_token: datatypes.IdTokenType
    remote_start_id: Optional[int]
    evse_id: Optional[int] = None
    group_id_token: Optional[datatypes.IdTokenType] = None
    charging_profile: Optional[datatypes.ChargingProfileType] = None

@dataclass
class TriggerMessage_Payload:
    requested_message: enums.MessageTriggerType
    evse: Optional[datatypes.EVSEType] = None

@dataclass
class SetChargingProfilePayload:
    evse_id: int
    charging_profile: datatypes.ChargingProfileType


@dataclass
class GetCompositeSchedulePayload:
    duration: int
    evse_id: int
    charging_rate_unit: Optional[enums.ChargingRateUnitType] = None


@dataclass
class GetChargingProfilesPayload:
    request_id: int
    charging_profile: datatypes.ChargingProfileCriterionType
    evse_id: Optional[int] = None


@dataclass
class ClearChargingProfilePayload:
    charging_profile_id: Optional[int] = None
    charging_profile_criteria: Optional[datatypes.ClearChargingProfileType] = None

@dataclass
class GetBaseReportPayload:
    report_base: enums.ReportBaseType
    request_id: Optional[int] = None


@dataclass
class ChangeAvailabilityPayload:
    operational_status: enums.OperationalStatusType
    evse: Optional[datatypes.EVSEType] = None

@dataclass
class SetVariableMonitoringPayload:
    set_monitoring_data: List[datatypes.SetMonitoringDataType]

@dataclass
class ClearVariableMonitoringPayload:
    id: List[int]