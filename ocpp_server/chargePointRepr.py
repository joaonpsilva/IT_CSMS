from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call, call_result, enums, datatypes
from ocpp.routing import on, after

from datetime import datetime
import asyncio

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
            "REQUEST_STOP_TRANSACTION" : self.requestStopTransaction,
            "TRIGGER_MESSAGE" : self.trigger_message
        }

        self.out_of_order_transaction = set([])
    
    async def send_CP_Message(self, method, payload):
        """Funtion will use the mapping defined in method_mapping to call the correct function"""
        return await self.method_mapping[method](payload=payload)

    
    async def get_authorization_relevant_info(self, payload):
        content = {"id_token" : payload["id_token"]}

        if "evse_id" in payload:
            content["evse_id"] = payload["evse_id"]
        elif "evse" in payload:
            content["evse_id"] = payload["evse"]["id"]
        
        message = ChargePoint.broker.build_message("Authorize_IdToken", self.id, content)

        response = await ChargePoint.broker.send_request_wait_response(message)
        
        return response["CONTENT"]["id_token_info"]


    async def guarantee_transaction_integrity(self, transaction_id):

        message = ChargePoint.broker.build_message("VERIFY_RECEIVED_ALL_TRANSACTION", self.id, {"transaction_id" : transaction_id})

        response = await ChargePoint.broker.send_request_wait_response(message)

        if response["CONTENT"]["status"] == "OK":
            return True
        elif response["CONTENT"]["status"] == "ERROR":
            logging.info("DB could not identify transaction")
        
        return False
                



#######################Functions starting from CSMS Initiative


    async def getVariables(self, payload):
        """Funtion initiated by the csms to get variables"""
        request = call.GetVariablesPayload(get_variable_data=payload['get_variable_data'])
        return await self.call(request)
    
    async def setVariables(self, payload):
        request = call.SetVariablesPayload(set_variable_data=payload['set_variable_data'])
        return await self.call(request)
    

    async def requestStartTransaction(self, payload):
        
        id_token_info = await self.get_authorization_relevant_info(payload)

        if id_token_info["status"] != enums.AuthorizationStatusType.accepted:
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
    

    async def trigger_message(self, payload):
        if payload["requested_message"] == enums.MessageTriggerType.status_notification and ("evse" in payload and payload["evse"]):
            try:
                assert(payload["evse"]["connector_id"] != None)
            except:
                return "Connector ID is required for status_notification"

        request = call.TriggerMessagePayload(**payload)
        return await self.call(request)

    async def getTransactionStatus(self, payload={}, transaction_id=None):

        if transaction_id is not None:
            payload["transaction_id"] = transaction_id
        
        request = call.GetTransactionStatusPayload(**payload)
        return await self.call(request)
    
    async def SetChargingProfile(self, payload):
        request = call.SetChargingProfilePayload(**payload)
        return await self.call(request)



#######################Funtions staring from the CP Initiative

    @on('BootNotification')
    async def on_BootNotification(self, **kwargs):

        message = ChargePoint.broker.build_message("BootNotification", self.id, kwargs)

        #inform db that new cp has connected
        await ChargePoint.broker.send_to_DB(message)

        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status='Accepted'
        )

    @on('StatusNotification')
    async def on_StatusNotification(self, **kwargs):

        message = ChargePoint.broker.build_message("StatusNotification", self.id, kwargs)

        #inform db that new cp has connected
        await ChargePoint.broker.send_to_DB(message)
        
        return call_result.StatusNotificationPayload()

    
    @on('MeterValues')
    async def on_MeterValues(self, **kwargs):

        message = ChargePoint.broker.build_message("MeterValues", self.id, kwargs)

        #inform db that new cp has connected
        await ChargePoint.broker.send_to_DB(message)

        return call_result.MeterValuesPayload()

    
    @on('Authorize')
    async def on_Authorize(self, **kwargs):

        message = ChargePoint.broker.build_message("Authorize_IdToken", self.id, kwargs)

        response = await ChargePoint.broker.send_request_wait_response(message)

        return call_result.AuthorizePayload(**response["CONTENT"])
        
    @on('TransactionEvent')
    async def on_TransactionEvent(self, **kwargs):
        
        message = ChargePoint.broker.build_message("TransactionEvent", self.id, kwargs)

        await ChargePoint.broker.send_to_DB(message)

        transaction_response = call_result.TransactionEventPayload()

        if "id_token" in kwargs:
            transaction_response.id_token_info = await self.get_authorization_relevant_info(kwargs)
        
        if kwargs["event_type"] == enums.TransactionEventType.ended:
            #Payment (show total cost)
            pass
        
        return transaction_response
    
    @after('TransactionEvent')
    async def after_TransactionEvent(self, **kwargs):
        transaction_id =  kwargs["transaction_info"]["transaction_id"]

        if kwargs["event_type"] == enums.TransactionEventType.ended or transaction_id in self.out_of_order_transaction:
            #verify that all messages have been received
            transaction_status = await self.getTransactionStatus(transaction_id=transaction_id)
            if transaction_status.messages_in_queue == True:
                #CP still holding messages
                self.out_of_order_transaction.add(transaction_id)
            else:
                #verify in db if we have all messages
                all_messages_received = await self.guarantee_transaction_integrity(transaction_id)
                if not all_messages_received:
                    logging.info("Messages lost for transaction %s", transaction_id)




    @on('Heartbeat')
    async def on_Heartbeat(self):
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().isoformat()
        )
    
