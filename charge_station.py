import asyncio
import logging
import websockets
from ocpp.routing import after,on
import sys
from datetime import datetime
from aioconsole import ainput

from ocpp.v201 import call, call_result, enums, datatypes
from ocpp.v201 import ChargePoint as cp

logging.basicConfig(level=logging.INFO)


class ChargePoint(cp):

    async def cold_Boot(self):

        request = call.BootNotificationPayload(
                    charging_station=datatypes.ChargingStationType(
                        vendor_name="vendor_name",
                        model="model"
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
    
    
    async def startTransaction_CablePluginFirst(self):

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
                id="AB1234",
                charging_state=enums.ChargingStateType.ev_connected
            ),
            evse=datatypes.EVSEType(id=1, connector_id=1)
            
        )
        response = await self.call(request)

        logging.info("User authorization successful")

        request = call.TransactionEventPayload(
            event_type=enums.TransactionEventType.updated,
            timestamp=datetime.utcnow().isoformat(),
            trigger_reason=enums.TriggerReasonType.authorized,
            seq_no=2,
            id_token=datatypes.IdTokenType(id_token="1234", type=enums.IdTokenType.central),
            transaction_info=datatypes.TransactionType(
                id="AB1234",
                charging_state=enums.ChargingStateType.ev_connected
            )
        )
        response = await self.call(request)


        request = call.TransactionEventPayload(
            event_type=enums.TransactionEventType.updated,
            timestamp=datetime.utcnow().isoformat(),
            trigger_reason=enums.TriggerReasonType.charging_state_changed,
            seq_no=3,
            id_token=datatypes.IdTokenType(id_token="1234", type=enums.IdTokenType.central),
            transaction_info=datatypes.TransactionType(
                id="AB1234",
                charging_state=enums.ChargingStateType.charging
            )
        )
        response = await self.call(request)
    
    async def authorizeRequest(self):
        request = call.AuthorizePayload(
            id_token=datatypes.IdTokenType(
                id_token="AAA",
                type=enums.IdTokenType.central
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





async def get_input(cp):
    
    command_map={
        "meterValuesRequest":cp.meterValuesRequest
    }

    while True:
        command = await ainput("")
        if command in command_map:
            await command_map[command]()


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