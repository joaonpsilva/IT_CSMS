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
            "TRIGGER_MESSAGE" : self.triggerMessage,
            "SET_CHARGING_PROFILE" : self.setChargingProfile,
            "GET_COMPOSITE_SCHEDULE" : self.getCompositeSchedule
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
        

        if "evse_id" in payload and payload["evse_id"] is not None and payload["evse_id"] <= 0:
            return "evse id must be > 0"

        if "charging_profile" in payload and payload["charging_profile"] is not None:
            #F01.FR.08
            if payload["charging_profile"]["charging_profile_purpose"] != enums.ChargingProfilePurposeType.tx_profile:
                return "charging profile needs to be TxProfile"
            #F01.FR.11
            if "transaction_id" in payload["charging_profile"] and payload["charging_profile"]["transaction_id"] is not None:
                return "Transaction id shall not be set"

        #creating an id for the request
        if "remote_start_id" not in payload or payload["remote_start_id"] is None:
            payload["remote_start_id"] = ChargePoint.new_remoteStartId()

        request = call.RequestStartTransactionPayload(**payload)
        response = await self.call(request)

        #Send to db??????????
        if "charging_profile" in payload and payload["charging_profile"] is not None and \
            "evse_id" in payload and payload["evse_id"] is not None and \
            response["status"] == enums.RequestStartStopStatusType.accepted:

            payload["charging_profile"]["transaction_id"] = response["transaction_id"] if response["transaction_id"] is not None else payload["remote_start_id"]
            
            m = {"evse_id": payload["evse_id"], "charging_profile":payload["charging_profile"]}
            message = ChargePoint.broker.build_message("SetChargingProfile", self.id, payload)
            await ChargePoint.broker.send_to_DB(message)

        return response
    
    async def requestStopTransaction(self, payload):

        request = call.RequestStopTransactionPayload(**payload)
        return await self.call(request)
    

    async def triggerMessage(self, payload):
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
        
    
    async def setChargingProfile(self, payload):
        #TODO revisit document
        #K01.FR.34, K01.FR.35, K01.FR.38, K01.FR.18, K01.FR.19, K01.FR.20

        #DB bug
        if payload["charging_profile"]["id"] == 0:
            return "ID cannot be 0"
        for schedule in payload["charging_profile"]["charging_schedule"]:
            if schedule["id"] == 0:
                return "ID cannot be 0"


        if payload["charging_profile"]["charging_profile_purpose"] == enums.ChargingProfilePurposeType.tx_profile:
            #K01.FR.03
            if "transaction_id" not in payload["charging_profile"] or payload["charging_profile"]["transaction_id"] is None:
                return "tx_profile needs tansaction id"
            
            #K01.FR.16
            if payload["evse_id"] == 0:
                return "TxProfile SHALL only be be used with evseId >0."
            
        else:
            if "transaction_id" in payload["charging_profile"] and payload["charging_profile"]["transaction_id"] is not None:
                return "only tx_profile can have tansaction id"

        #K01.FR.06, K01.FR.39
        relevant = {"evse_id": payload["evse_id"]}
        relevant["charging_profile"] = {key: value for key, value in payload["charging_profile"].items() if key in ["id", "stack_level", "charging_profile_purpose", "valid_from", "valid_to"]}
        message = ChargePoint.broker.build_message("VERIFY_CHARGING_PROFILE_CONFLICTS", self.id, relevant)
        response = await ChargePoint.broker.send_request_wait_response(message)
        if len(response["CONTENT"]["conflict_ids"]) != 0:
            return "profile conflicts with existing profile"
        

        request = call.SetChargingProfilePayload(**payload)
        response = await self.call(request)

        if response.status == enums.ChargingProfileStatus.accepted:
            message = ChargePoint.broker.build_message("SetChargingProfile", self.id, payload)
            await ChargePoint.broker.send_to_DB(message)
        
        return response
    
    async def getCompositeSchedule(self, payload):

        request = call.GetCompositeSchedulePayload(**payload)
        return await self.call(request)




#######################Funtions staring from the CP Initiative

    @on('BootNotification')
    async def on_BootNotification(self, **kwargs):

        #inform db that new cp has connected
        message = ChargePoint.broker.build_message("BootNotification", self.id, kwargs)
        await ChargePoint.broker.send_to_DB(message)

        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status='Accepted'
        )

    @on('StatusNotification')
    async def on_StatusNotification(self, **kwargs):

        #inform db that new cp has connected
        message = ChargePoint.broker.build_message("StatusNotification", self.id, kwargs)
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
    
