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
    

    async def transactionEventRequest(self):
        request = call.TransactionEventPayload(
            event_type=enums.TransactionEventType.started,
            timestamp=datetime.utcnow().isoformat(),
            trigger_reason=enums.TriggerReasonType.ev_detected,
            seq_no=1,
            transaction_info=datatypes.TransactionType(
                id="123"
            )
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

    @on('GetVariables')
    def on_get_variables(self,get_variable_data,**kwargs):

        logging.info("Received GetVariables")

        get_variable_result=[]

        for var in get_variable_data:
            get_variable_result.append(
                {
                    'attribute_status': enums.GetVariableStatusType.accepted, 
                    'attribute_value' : 'ATRIBUTE_VALUE',
                    'component' : {
                        'name': var.get('component').get('name')
                    },
                    'variable' : {
                        'name': var.get('variable').get('name')
                    }
                }
                        
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

    @on('GetTransactionStatus')
    def on_GetTransactionStatus(self,**kwargs):

        logging.info("Received GetTransactionStatus")

        return call_result.GetTransactionStatusPayload(
            messages_in_queue=True,
            ongoing_indicator=True
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