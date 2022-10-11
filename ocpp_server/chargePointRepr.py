from calendar import c
from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call, call_result, enums, datatypes

from ocpp.routing import on
from datetime import datetime
from datetime import datetime

import logging

from requests import request
logging.basicConfig(level=logging.INFO)


class ChargePoint(cp):

    broker = None

    def __init__(self, id, connection, response_timeout=30):
        super().__init__(id, connection, response_timeout)

        self.method_mapping = {
            "GET_VARIABLES" : self.getVariables,
            "GET_TRANSACTION_STATUS" : self.getTransactionStatus,
            "SET_VARIABLES" : self.setVariables,
            "REQUEST_START_TRANSACTION" : self.requestStartTransaction
        }
    
    async def send_CP_Message(self, method, payload):
        """Funtion will use the mapping defined in method_mapping to call the correct function"""
        return await self.method_mapping[method](payload)



#######################Functions starting from CSMS Initiative


    async def getVariables(self, payload):
        """Funtion initiated by the csms to get variables"""
        request = call.GetVariablesPayload(get_variable_data=payload['get_variable_data'])
        return await self.call(request)
    
    async def setVariables(self, payload):
        request = call.SetVariablesPayload(set_variable_data=payload['set_variable_data'])
        return await self.call(request)

    
    async def getTransactionStatus(self, payload={'transaction_id' : None}):

        transaction_id = payload['transaction_id'] if 'transaction_id' in payload else None

        request = call.GetTransactionStatusPayload(transaction_id=transaction_id)
        return await self.call(request)
    

    async def requestStartTransaction(self, payload):

        evse_id = payload['evse_id'] if 'evse_id' in payload else None
        charging_profile = payload['charging_profile'] if 'charging_profile' in payload else None
        group_id_token = payload['group_id_token'] if 'group_id_token' in payload else None

        request = call.RequestStartTransactionPayload(
            id_token=payload['id_token'],
            remote_start_id=payload['remote_start_id'],
            evse_id=evse_id,
            group_id_token=group_id_token,
            charging_profile=charging_profile
        )
        return await self.call(request)






#######################Funtions staring from the CP Initiative


    @on('BootNotification')
    async def on_BootNotification(self, charging_station, reason, **kwargs):

        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status='Accepted'
        )
    
    @on('MeterValues')
    async def on_MeterValues(self, evse_id, meter_value):
        #what TODO with parameters
        await ChargePoint.broker.send_to_DB({
            "METHOD" : "METER_VALUES",
            "CONTENT" : {
                "evse_id" : evse_id,
                "meter_value": meter_value
            }
        })

        return call_result.MeterValuesPayload()
    
    @on('TransactionEvent')
    async def on_TransactionEvent(self, event_type, timestamp, trigger_reason, seq_no, transaction_info, **kwargs):
        #TODO construct better TransactionEventPayload
        return call_result.TransactionEventPayload()
    
    @on('StatusNotification')
    async def on_StatusNotification(self, timestamp, connector_status, evse_id, connector_id):
        #what TODO with parameters
        return call_result.StatusNotificationPayload()

    @on('Heartbeat')
    async def on_Heartbeat(self):
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().isoformat()
        )
    
    @on('Authorize')
    async def on_Authorize(self,id_token, **kwargs):
        return call_result.AuthorizePayload(
            id_token_info=datatypes.IdTokenInfoType(
                status=enums.AuthorizationStatusType.accepted
            )
        )