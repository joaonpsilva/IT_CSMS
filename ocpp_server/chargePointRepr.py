from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call, call_result, enums, datatypes

from ocpp.routing import on
from datetime import datetime

import logging

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

    def build_message(self, method, content):
        message = {
            "METHOD" : method,
            "CP_ID" : self.id,
            "CONTENT" : content
        }

        return message


    @on('BootNotification')
    async def on_BootNotification(self, **kwargs):

        message = self.build_message("BootNotification", kwargs)

        #inform db that new cp has connected
        await ChargePoint.broker.send_to_DB(message)

        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status='Accepted'
        )

    @on('StatusNotification')
    async def on_StatusNotification(self, **kwargs):

        message = self.build_message("StatusNotification", kwargs)

        #inform db that new cp has connected
        await ChargePoint.broker.send_to_DB(message)
        
        return call_result.StatusNotificationPayload()

    
    @on('MeterValues')
    async def on_MeterValues(self, **kwargs):

        message = self.build_message("MeterValues", kwargs)

        #inform db that new cp has connected
        await ChargePoint.broker.send_to_DB(message)

        return call_result.MeterValuesPayload()
    
    @on('Authorize')
    async def on_Authorize(self, **kwargs):

        message = self.build_message("Authorize", kwargs)

        response = await ChargePoint.broker.send_request_wait_response(message)
        content = response["CONTENT"]

        if content is None:
            status = enums.AuthorizationStatusType.unknown
            content = {}
        elif "evse_id" in content and len(content["evse_id"]):
            status = enums.AuthorizationStatusType.not_at_this_location
        elif "cache_expiry_date_time" in content and content["cache_expiry_date_time"] < datetime.utcnow().isoformat():
            status = enums.AuthorizationStatusType.invalid
        else: 
            status = enums.AuthorizationStatusType.accepted

        return call_result.AuthorizePayload(
            id_token_info=datatypes.IdTokenInfoType(
                status=status,
                **content
            )
        )
    
    @on('TransactionEvent')
    async def on_TransactionEvent(self, event_type, timestamp, trigger_reason, seq_no, transaction_info, **kwargs):
        #TODO construct better TransactionEventPayload
        return call_result.TransactionEventPayload()
    

    @on('Heartbeat')
    async def on_Heartbeat(self):
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().isoformat()
        )
    
