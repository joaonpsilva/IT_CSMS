from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call, call_result, enums, datatypes

from ocpp.routing import on
from datetime import datetime

import logging

logging.basicConfig(level=logging.INFO)


class ChargePoint(cp):

    broker = None
    remoteStartId = 0

    def read_variables():
        #TODO read variables (remoteStartId) from file
        pass

    def new_remoteStartId():
        ChargePoint.remoteStartId += 1
        return ChargePoint.remoteStartId


    def __init__(self, id, connection, response_timeout=30):
        super().__init__(id, connection, response_timeout)

        self.method_mapping = {
            "GET_VARIABLES" : self.getVariables,
            "GET_TRANSACTION_STATUS" : self.getTransactionStatus,
            "SET_VARIABLES" : self.setVariables,
            "REQUEST_START_TRANSACTION" : self.requestStartTransaction,
            "REQUEST_STOP_TRANSACTION" : self.requestStopTransaction
        }

    
    async def send_CP_Message(self, method, payload):
        """Funtion will use the mapping defined in method_mapping to call the correct function"""
        return await self.method_mapping[method](payload)

    
    def get_authorization_relevant_info(self, payload):
        content = {"id_token" : payload["id_token"]}

        if "evse_id" in payload:
            content["evse_id"] = payload["evse_id"]
        elif "evse" in payload:
            content["evse_id"] = payload["evse"]["id"]
        
        return content




#######################Functions starting from CSMS Initiative


    async def getVariables(self, payload):
        """Funtion initiated by the csms to get variables"""
        request = call.GetVariablesPayload(get_variable_data=payload['get_variable_data'])
        return await self.call(request)
    
    async def setVariables(self, payload):
        request = call.SetVariablesPayload(set_variable_data=payload['set_variable_data'])
        return await self.call(request)

    
    async def getTransactionStatus(self, payload={'transaction_id' : None}):

        request = call.GetTransactionStatusPayload(**payload)
        return await self.call(request)
    

    async def requestStartTransaction(self, payload):
        
        content = self.get_authorization_relevant_info(payload)

        message = self.build_message("Authorize_IdToken", content)
        response = await ChargePoint.broker.send_request_wait_response(message)
        if response["CONTENT"]["id_token_info"]["status"] != enums.AuthorizationStatusType.accepted:
            return "No Permission"


        #creating an id for the request
        payload["remote_start_id"] = ChargePoint.new_remoteStartId()

        request = call.RequestStartTransactionPayload(**payload)

        response = await self.call(request)
        #returning the created id
        response.remote_start_id = payload["remote_start_id"]

        return response
    
    async def requestStopTransaction(self, payload):

        request = call.RequestStopTransactionPayload(**payload)
        return await self.call(request)

    async def checkTransactionStatus(self, payload=None, idToken=None):

        if idToken is not None:
            payload["idToken"] = idToken
        
        request = call.GetTransactionStatusPayload(**payload)
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

        message = self.build_message("Authorize_IdToken", kwargs)
        response = await ChargePoint.broker.send_request_wait_response(message)

        return call_result.AuthorizePayload(**response["CONTENT"])
    
    @on('TransactionEvent')
    async def on_TransactionEvent(self, **kwargs):
        
        message = self.build_message("TransactionEvent", kwargs)
        await ChargePoint.broker.send_to_DB(message)
        transactionEventPayload = call_result.TransactionEventPayload()

        if "id_token" in kwargs:
            content = self.get_authorization_relevant_info(kwargs)    
            message = self.build_message("Authorize_IdToken", content)
            response = await ChargePoint.broker.send_request_wait_response(message)
            transactionEventPayload = call_result.TransactionEventPayload(**response["CONTENT"])
        
        #TODO on last message check if all messages received
        #TODO billing

        return transactionEventPayload
    

    @on('Heartbeat')
    async def on_Heartbeat(self):
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().isoformat()
        )
    
