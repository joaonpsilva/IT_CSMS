import asyncio
import logging
import websockets
from ocpp.routing import after,on
import sys
from datetime import datetime
from aioconsole import ainput
import string
import random

from ocpp.v201 import call, call_result, enums, datatypes
from ocpp.v201 import ChargePoint as cp

logging.basicConfig(level=logging.INFO)


class ChargePoint(cp):

    def __init__(self, cp_id, ws):
        super().__init__(cp_id, ws)
        self.messages_in_queue=False

        self.variables = {
            "DeviceDataCtrlrItemsPerMessageGetVariablesActual" : 10,
            "DeviceDataCtrlrItemsPerMessageSetVariablesActual" : 10,
            "MonitoringCtrlrBytesPerMessageSetVariableMonitoringActual" : 1000,
            "MonitoringCtrlrItemsPerMessageSetVariableMonitoringActual" : 10,
            "MonitoringCtrlrItemsPerMessageClearVariableMonitoringActual" : 10,
            "MonitoringCtrlrBytesPerMessageClearVariableMonitoringActual" : 1000,
            "LocalAuthListCtrlrItemsPerMessageActual":10,
            "LocalAuthListCtrlrBytesPerMessageActual":1000
        }

        self.version_number=0

    async def cold_Boot(self):

        request = call.BootNotificationPayload(
                    charging_station=datatypes.ChargingStationType(
                        vendor_name="vendor_name",
                        model="model",
                        modem=datatypes.ModemType(
                            iccid="jklasdfhlkjashdl"
                        )
                    ),
                    reason=enums.BootReasonType.power_up
                )

        response = await self.call(request)

        if response.status == 'Accepted':
           logging.info("Connected to central system.")

        for i in range(3):
            request = call.StatusNotificationPayload(
                timestamp=datetime.utcnow().isoformat(),
                evse_id=1,
                connector_id=i,
                connector_status=enums.ConnectorStatusType.available
            )
            response = await self.call(request)



    
    async def meterValuesRequest(self):

        request = call.MeterValuesPayload(
            evse_id = 1,
            meter_value = [
                datatypes.MeterValueType(
                    timestamp=datetime.utcnow().isoformat(),
                    sampled_value=[
                        datatypes.SampledValueType(
                            value=0.1,
                            measurand = enums.MeasurandType.current_export,
                        )
                    ]
                )
            ]
        )
        response = await self.call(request)
    


    
    async def authorizeRequest(self):
        request = call.AuthorizePayload(
            id_token=datatypes.IdTokenType(
                id_token="123456789",
                type=enums.IdTokenType.iso14443
            )
        )
        
        response = await self.call(request)
        return response.id_token_info['status'] == "Accepted"
    


    
    async def unsorted_transaction(self):

        transaction_id = ''.join(random.choice(string.ascii_letters) for i in range(10))

        request = call.StatusNotificationPayload(
            timestamp=datetime.utcnow().isoformat(),
            connector_status=enums.ConnectorStatusType.occupied,
            evse_id=1,
            connector_id=1
        )
        response = await self.call(request)


        request = call.TransactionEventPayload(
            event_type=enums.TransactionEventType.started,
            timestamp=datetime.utcnow().isoformat(),
            trigger_reason=enums.TriggerReasonType.cable_plugged_in,
            seq_no=1,
            transaction_info=datatypes.TransactionType(
                transaction_id=transaction_id,
                charging_state=enums.ChargingStateType.ev_connected
            ),
            evse=datatypes.EVSEType(id=1, connector_id=1)
            
        )
        response = await self.call(request)

        if await self.authorizeRequest():
            logging.info("User authorization successful")
        else:
            logging.info("User authorization unsuccessful")
            return 


        request = call.TransactionEventPayload(
            event_type=enums.TransactionEventType.ended,
            timestamp=datetime.utcnow().isoformat(),
            trigger_reason=enums.TriggerReasonType.ev_departed,
            seq_no=3,
            id_token=datatypes.IdTokenType(
                id_token="123456789",
                type=enums.IdTokenType.iso14443
            ),
            transaction_info=datatypes.TransactionType(
                transaction_id=transaction_id,
                charging_state=enums.ChargingStateType.idle
            )
        )
        
        self.messages_in_queue=True

        response = await self.call(request)
    
    
    async def startTransaction_CablePluginFirst(self):

        transaction_id = ''.join(random.choice(string.ascii_letters) for i in range(10))

        request = call.StatusNotificationPayload(
            timestamp=datetime.utcnow().isoformat(),
            connector_status=enums.ConnectorStatusType.occupied,
            evse_id=1,
            connector_id=1
        )
        response = await self.call(request)


        request = call.TransactionEventPayload(
            event_type=enums.TransactionEventType.started,
            timestamp=datetime.utcnow().isoformat(),
            trigger_reason=enums.TriggerReasonType.cable_plugged_in,
            seq_no=1,
            transaction_info=datatypes.TransactionType(
                transaction_id=transaction_id,
                charging_state=enums.ChargingStateType.ev_connected
            ),
            evse=datatypes.EVSEType(id=1, connector_id=1)
            
        )
        response = await self.call(request)

        if await self.authorizeRequest():
            logging.info("User authorization successful")
        else:
            logging.info("User authorization unsuccessful")
            return 

        request = call.TransactionEventPayload(
            event_type=enums.TransactionEventType.updated,
            timestamp=datetime.utcnow().isoformat(),
            trigger_reason=enums.TriggerReasonType.authorized,
            seq_no=2,
            id_token=datatypes.IdTokenType(
                id_token="123456789",
                type=enums.IdTokenType.iso14443
            ),
            transaction_info=datatypes.TransactionType(
                transaction_id=transaction_id,
                charging_state=enums.ChargingStateType.charging
            )
        )
        response = await self.call(request)
        if response.id_token_info['status'] != "Accepted":
            logging.info("User authorization unsuccessful on 2nd check")
            return 

        request = call.TransactionEventPayload(
            event_type=enums.TransactionEventType.ended,
            timestamp=datetime.utcnow().isoformat(),
            trigger_reason=enums.TriggerReasonType.ev_departed,
            seq_no=3,
            id_token=datatypes.IdTokenType(
                id_token="123456789",
                type=enums.IdTokenType.iso14443
            ),
            transaction_info=datatypes.TransactionType(
                transaction_id=transaction_id,
                charging_state=enums.ChargingStateType.idle
            )
        )
        response = await self.call(request)
    


########################################

    def total_name(self, component, variable, type):
        s=""

        s += component["name"] if "name" in component else ""
        s += component["instance"] if "instance" in component else ""
        s += variable["name"] if "name" in variable else ""
        s += variable["instance"] if "instance" in variable else ""
        s += type

        return s

    @on('GetVariables')
    def on_get_variables(self,get_variable_data,**kwargs):

        get_variable_result=[]

        for var in get_variable_data:

            variable = var['variable']
            component = var['component']
            type = var['attribute_type'] if 'attribute_type' in var else 'Actual'

            status = enums.GetVariableStatusType.unknown_variable
            value = None

            total_name = self.total_name(component, variable,type)
            if total_name in self.variables:
                status = enums.GetVariableStatusType.accepted
                value = str(self.variables[total_name])

            get_variable_result.append(
                datatypes.GetVariableResultType(
                    attribute_status= status, 
                    attribute_value = value,
                    component=component,
                    variable= variable,
                    attribute_type=type
                )   
            )

        return call_result.GetVariablesPayload(get_variable_result=get_variable_result)
    

    @on('SetVariables')
    def on_set_variables(self, set_variable_data):

        return call_result.SetVariablesPayload(
            set_variable_result=[
                datatypes.SetVariableResultType(
                    attribute_status=enums.SetVariableStatusType.accepted,
                    component=datatypes.ComponentType(
                        name="ABC"
                    ),
                    variable=datatypes.VariableType(
                        name="ABC"
                    )
                )
            ]
        )
    

    @on('RequestStartTransaction')
    def on_RequestStartTransaction(self, id_token, remote_start_id, **kwargs):

        return call_result.RequestStartTransactionPayload(
            status=enums.RequestStartStopStatusType.accepted
        )
    @after('RequestStartTransaction')
    async def after_RequestStartTransaction(self, id_token, remote_start_id, **kwargs):
        transaction_id = ''.join(random.choice(string.ascii_letters) for i in range(10))

        request = call.TransactionEventPayload(
            event_type=enums.TransactionEventType.started,
            timestamp=datetime.utcnow().isoformat(),
            trigger_reason=enums.TriggerReasonType.remote_start,
            seq_no=1,
            transaction_info=datatypes.TransactionType(
                transaction_id=transaction_id,
                charging_state=enums.ChargingStateType.ev_connected,
                remote_start_id=remote_start_id
            ),
            evse=datatypes.EVSEType(id=1, connector_id=1)
            
        )
        response = await self.call(request)

        
    
    @on('RequestStopTransaction')
    def on_RequestStopTransaction(self, transaction_id, **kwargs):

        return call_result.RequestStopTransactionPayload(
            status=enums.RequestStartStopStatusType.accepted
        )
    
    @on('TriggerMessage')
    def on_TriggerMessage(self, requested_message, **kwargs):

        return call_result.TriggerMessagePayload(
            status=enums.TriggerMessageStatusType.accepted
        )
    
    @on('GetTransactionStatus')
    def on_GetTransactionStatus(self, **kwargs):
        
        return call_result.GetTransactionStatusPayload(messages_in_queue=self.messages_in_queue)
    
    @after("GetTransactionStatus")
    async def wait_to_send_message(self, transaction_id):

        if self.messages_in_queue:
            self.messages_in_queue = False

            request = call.TransactionEventPayload(
                event_type=enums.TransactionEventType.updated,
                timestamp=datetime.utcnow().isoformat(),
                trigger_reason=enums.TriggerReasonType.authorized,
                seq_no=2,
                id_token=datatypes.IdTokenType(
                    id_token="123456789",
                    type=enums.IdTokenType.iso14443
                ),
                transaction_info=datatypes.TransactionType(
                    transaction_id=transaction_id,
                    charging_state=enums.ChargingStateType.charging
                )
            )
            response = await self.call(request)
    
    @on("SetChargingProfile")
    async def on_SetChargingProfile(self, evse_id, charging_profile):
        return call_result.SetChargingProfilePayload(status=enums.ChargingProfileStatus.accepted)

    @on("GetCompositeSchedule")
    async def on_GetCompositeSchedule(self, duration, evse_id, **kwargs):
        return call_result.GetCompositeSchedulePayload(status=enums.GenericStatusType.accepted)

    @on("GetChargingProfiles")
    async def on_GetChargingProfiles(self, request_id, charging_profile, **kwargs):
        return call_result.GetChargingProfilesPayload(status=enums.GenericStatusType.accepted)

    @after("GetChargingProfiles")
    async def after_GetChargingProfiles(self, request_id, charging_profile, **kwargs):

        charge_profile = {
                        "id": 0,
                        "stack_level": 0,
                        "charging_profile_purpose": "ChargingStationExternalConstraints",
                        "charging_profile_kind": "Absolute",
                        "charging_schedule": [
                        {
                            "id": 0,
                            "charging_rate_unit": "W",
                            "charging_schedule_period": [
                            {
                                "start_period": 0,
                                "limit": 0,
                                "number_phases": 0,
                                "phase_to_use": 0
                                }]}]}

        request = call.ReportChargingProfilesPayload(
            request_id = request_id,
            charging_limit_source = enums.ChargingLimitSourceType.cso,
            tbc = True,
            evse_id = 0,
            charging_profile = [charge_profile]
        )


            
        response = await self.call(request)

        request = call.ReportChargingProfilesPayload(
            request_id = request_id,
            charging_limit_source = enums.ChargingLimitSourceType.cso,
            tbc = False,
            evse_id = 0,
            charging_profile = [charge_profile]
        )
        response = await self.call(request)
    
    @on("ClearChargingProfile")
    async def on_ClearChargingProfileRequest(self, **kwargs):
        return call_result.ClearChargingProfilePayload(status=enums.ClearChargingProfileStatusType.accepted)
    

    @on("GetBaseReport")
    async def on_GetBaseReport(self, request_id,**kwargs):
        return call_result.GetBaseReportPayload(status=enums.GenericDeviceModelStatusType.accepted)
    
    @after("GetBaseReport")
    async def after_GetBaseReport(self, request_id,**kwargs):

        request = call.NotifyReportPayload(
            request_id=request_id,
            generated_at=datetime.utcnow().isoformat(),
            tbc = True,
            seq_no=0,
            report_data=[datatypes.ReportDataType(
                component=datatypes.ComponentType(
                    name="AAAA"
                ),
                variable=datatypes.VariableType(
                    name="AAA"
                ),
                variable_attribute=[datatypes.VariableAttributeType()]
            )]
        )
        response = await self.call(request)

        request = call.NotifyReportPayload(
            request_id=request_id,
            generated_at=datetime.utcnow().isoformat(),
            tbc = False,
            seq_no=1,
            report_data=[datatypes.ReportDataType(
                component=datatypes.ComponentType(
                    name="BBBBB"
                ),
                variable=datatypes.VariableType(
                    name="BBB"
                ),
                variable_attribute=[datatypes.VariableAttributeType()]
            )]
        )
        response = await self.call(request)
    
    @on("ChangeAvailability")
    async def on_ChangeAvailability(self,operational_status, **kwargs):
        return call_result.ChangeAvailabilityPayload(status=enums.ChangeAvailabilityStatusType.accepted)
    

    @after("ChangeAvailability")
    async def after_ChangeAvailability(self, operational_status, **kwargs):

        connector_status = enums.ConnectorStatusType.available
        if operational_status == enums.OperationalStatusType.inoperative:
            connector_status = enums.ConnectorStatusType.unavailable

        connectors = [0, 1, 2]
        if "evse" in kwargs and "connector_id" in kwargs["evse"]:
            connectors = [kwargs["evse"]["connector_id"]]
        
        for i in connectors:
            request = call.StatusNotificationPayload(
                timestamp=datetime.utcnow().isoformat(),
                connector_status=connector_status,
                evse_id=1,
                connector_id=i
            )
            response = await self.call(request)
    
    @on("SetVariableMonitoring")
    async def on_SetVariableMonitoring(self, set_monitoring_data, **kwargs):

        result = []
        id = 0
        for data in set_monitoring_data:
            id+=1

            result.append(datatypes.SetMonitoringResultType(
                id=id,
                status=enums.SetMonitoringStatusType.accepted,
                type=data["type"],
                severity=data["severity"],
                component=data["component"],
                variable=data["variable"]
            ))

        return call_result.SetVariableMonitoringPayload(set_monitoring_result=result)
    

    @on("Reset")
    async def on_Reset(self, type, **kwargs):
        return call_result.ResetPayload(status=enums.ResetStatusType.accepted)



    @on("ClearVariableMonitoring")
    async def on_ClearVariableMonitoring(self, id, **kwargs):

        result = []
        for monitor_id in id:

            result.append(datatypes.ClearMonitoringResultType(
                status=enums.ClearMessageStatusType.accepted,
                id=monitor_id,
            ))

        return call_result.ClearVariableMonitoringPayload(clear_monitoring_result=result)
    
    @on("GetLocalListVersion")
    async def on_GetLocalListVersion(self):
        return call_result.GetLocalListVersionPayload(version_number=self.version_number)
    
    @on("SendLocalList")
    async def on_SendLocalList(self, **kwargs):
        return call_result.SendLocalListPayload(status=enums.SendLocalListStatusType.accepted)
    
    @on("SetDisplayMessage")
    async def on_SetDisplayMessage(self, **kwargs):
        return call_result.SetDisplayMessagePayload(status=enums.DisplayMessageStatusType.accepted)
    
    @on("GetDisplayMessages")
    async def on_GetDisplayMessages(self, **kwargs):
        return call_result.GetDisplayMessagesPayload(status=enums.GetDisplayMessagesStatusType.accepted)
    
    @after("GetDisplayMessages")
    async def after_GetDisplayMessages(self, request_id, **kwargs):

        request = call.NotifyDisplayMessagesPayload(
            request_id=request_id,
            tbc=True,
            message_info=[datatypes.MessageInfoType(
                id = 1,
                priority=enums.MessagePriorityType.normal_cycle,
                message=datatypes.MessageContentType(
                    format=enums.MessageFormatType.utf8,
                    content="Welcome"
                )
            )]
        )

        await self.call(request)

        request = call.NotifyDisplayMessagesPayload(
            request_id=request_id,
            tbc=False,
            message_info=[datatypes.MessageInfoType(
                id = 2,
                priority=enums.MessagePriorityType.normal_cycle,
                message=datatypes.MessageContentType(
                    format=enums.MessageFormatType.utf8,
                    content="Goodbye"
                )
            )]
        )

        await self.call(request)
    
    @on("ClearDisplayMessage")
    async def on_ClearDisplayMessage(self, **kwargs):
        return call_result.ClearDisplayMessagePayload(status=enums.ClearMessageStatusType.accepted)
    

    @on("UnlockConnector")
    async def on_UnlockConnector(self, **kwargs):
        return call_result.UnlockConnectorPayload(status=enums.UnlockStatusType.unlocked)





async def get_input(cp):
    
    command_map={
        "meter_values":cp.meterValuesRequest,
        "authorize" : cp.authorizeRequest,
        "start_cable" : cp.startTransaction_CablePluginFirst,
        "start_unsorted" : cp.unsorted_transaction
    }

    while True:
        command = await ainput("")
        if command in command_map:
            await command_map[command]()
            logging.info("FINISHED %s", command)


async def main(cp_id):

    logging.info("Trying to connect to csms with id %s", cp_id)

    async with websockets.connect(
        'ws://{cp_id}:{password}@localhost:9000/{cp_id}'.format(cp_id = cp_id, password='passcp1'),
        
            subprotocols=['ocpp2.0.1']
    ) as ws:

        cp = ChargePoint(cp_id, ws)

        await asyncio.gather(cp.start(), cp.cold_Boot(), get_input(cp))




        


if __name__ == '__main__':
   asyncio.run(main(sys.argv[1]))