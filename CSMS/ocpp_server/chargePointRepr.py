from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call, call_result, enums, datatypes
from ocpp.routing import on, after
from variable_definitions import VARIABLES
from datetime import datetime
import asyncio
from dataclasses import asdict
import logging
import dateutil.parser
from sys import getsizeof
import traceback
from csms_Rabbit_Handler import Rabbit_Message

logging.basicConfig(level=logging.INFO)


class ChargePoint(cp):

    broker = None
    remoteStartId = 0
    request_Id = 0

    def read_variables():
        #TODO read variables (remoteStartId) from file
        pass

    def new_remoteStartId():
        ChargePoint.remoteStartId += 1
        return ChargePoint.remoteStartId
    
    def new_requestId():
        ChargePoint.request_Id += 1
        return ChargePoint.request_Id

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
            "GET_COMPOSITE_SCHEDULE" : self.getCompositeSchedule,
            "GET_CHARGING_PROFILES" : self.getChargingProfiles,
            "CLEAR_CHARGING_PROFILE": self.clearChargingProfile,
            "GET_BASE_REPORT" : self.getBaseReport,
            "CHANGE_AVAILABILITY" : self.changeAvailability,
            "SET_VARIABLE_MONITORING" : self.setVariableMonitoring,
            "CLEAR_VARIABLE_MONITORING" : self.clearVariableMonitoring,
            "RESET" : self.reset,
            "SEND_AUTHORIZATION_LIST" : self.send_auhorization_list,
            "SET_DISPLAY_MESSAGE" : self.setDisplayMessage,
            "GET_DISPLAY_MESSAGES" : self.getDisplayMessages,
            "CLEAR_DISPLAY_MESSAGE" : self.clearDisplayMessage,
            "UNLOCK_CONNECTOR" : self.unlockConnector
        }

        
        self.max_get_messages=None

        self.loop = asyncio.get_running_loop()
        self.out_of_order_transaction = set([])
        self.multiple_response_requests = {}
        self.wait_start_transaction = {}
    
    
    async def send_CP_Message(self, method, content={}, **kwargs):
        """Funtion will use the mapping defined in method_mapping to call the correct function"""
        try:
            return "OK", await self.method_mapping[method](payload=content)
        except ValueError as ve:
            return "VAL_ERROR", ve.args[0]
        except Exception as e:
            logging.error(traceback.format_exc())
            return "ERROR", None


    async def get_id_token_info(self, payload):
        """
        authorize id token
        args: dict with {"id_token": idtokentype}. Can also have evse_id or evse
        """

        content = {"id_token" : payload["id_token"]}

        if "evse_id" in payload:
            content["evse_id"] = payload["evse_id"]
        elif "evse" in payload:
            content["evse_id"] = payload["evse"]["id"]
        
        message = Rabbit_Message(method="Authorize", cp_id=self.id, content=content)
        response = await ChargePoint.broker.send_request_wait_response(message)
        if response["status"] == "OK":
            id_token_info = response["content"]["id_token_info"]
        else:
            id_token_info = {"status":enums.AuthorizationStatusType.invalid}
        
        return id_token_info


    async def guarantee_transaction_integrity(self, transaction_id):

        message = Rabbit_Message(method="VERIFY_RECEIVED_ALL_TRANSACTION", cp_id=self.id, content={"transaction_id" : transaction_id})
        response = await ChargePoint.broker.send_request_wait_response(message)

        if response["status"] == "OK":

            if response["content"]["status"] == "OK":
                return True
            logging.info("DB could not identify transaction")
            return False
        
        raise ValueError("DB ERROR")
        
    

    async def get_max_get_messages(self):
        if self.max_get_messages is None:
            request = call.GetVariablesPayload(get_variable_data=[
                datatypes.GetVariableDataType(
                    component=VARIABLES["ItemsPerMessageGetVariables"]["component"],
                    variable=VARIABLES["ItemsPerMessageGetVariables"]["variable"]
                )
            ])
            self.max_get_messages = int((await self.call(request)).get_variable_result[0]["attribute_value"])
            logging.info("Max number of getvariables supported is %d", self.max_get_messages)

        return self.max_get_messages

    
    async def sendListByChunks(self, Payload_type, request_dict, var_with_list, max_items=None, max_bytes=None):
        """
        Divide single request (that contains a list of items) in several smaller requests,
        in order to fullfill the limitations max_items and max_bytes per message

        Args:
        Payload_type: class of the payload call.*Payload
        request_dict: actual payload of the full message, should follow the ocpp guidelines
        var_with_list: attribute in which the list of items is
        max_items: max number of items in the list
        max_bytes: max number of bytes of the request
        """
        
        #get all the items in the request list
        item_list = [request_dict[var_with_list]]
        results = []
        flag=True

        while len(item_list) > 0:   #still more items to send
            #Build request with whole list
            #If too large, split in half and keep trying
            
            #get and delete first entry
            current_list = item_list[0] 
            del item_list[0]
            
            #Build request 
            request_dict[var_with_list] = current_list
            request = Payload_type(**request_dict)

            #exceeded restrictions
            if (max_items and len(request_dict[var_with_list]) > max_items) or \
                (max_bytes and getsizeof(request) > max_bytes):

                #message was as small as it could be
                if len(request_dict[var_with_list]) == 1:
                    raise ValueError("Charge Station doesnt allow a single item")

                #insert splitted entries
                half_of_list = len(current_list) // 2
                item_list.insert(0, current_list[half_of_list:len(current_list)])
                item_list.insert(0, current_list[0:half_of_list])

            else:
                #send
                results.append(await self.call(request))

                #special cases after 1st message
                if flag:
                    flag=False
                    if Payload_type == call.SendLocalListPayload:
                        request_dict["update_type"] = enums.UpdateType.differential
        
        return results


    async def getVariablesByName(self, variables):
        """
        getvariables by Name. Uses the name of the variable and builds a proper GetVariables request
        ARGS: List of var names (str) or tuple(name, enums.AttributeType)
        RETURNS dict with key name(str) or (name,enums.AttributeType) and value is what was returned in attribute_value
        If variable was not known, it will not be in the return
        """
        requests = []

        for variable in variables.copy():
            
            if isinstance(variable, tuple):
                variable_name = variable[0]
                type = variable[1]
            else:
                variable_name = variable
                type = enums.AttributeType.actual
            
            if variable_name in VARIABLES:
                requests.append(datatypes.GetVariableDataType(
                    component=VARIABLES[variable_name]["component"],
                    variable=VARIABLES[variable_name]["variable"],
                    attribute_type=type
                ))
            else:
                variables.remove(variable)
        
        results = await self.getVariables({"get_variable_data":requests})

        return {request: result['attribute_value'] for request, result in zip(variables, results["get_variable_result"]) 
            if result['attribute_status'] == enums.GetVariableStatusType.accepted}
        

#######################Functions starting from CSMS Initiative


    async def getVariables(self, payload):
        """Funtion initiated by the csms to get variables"""

        max_get_messages = await self.get_max_get_messages()

        results = await self.sendListByChunks(call.GetVariablesPayload, payload, "get_variable_data", max_get_messages)
        result = {"get_variable_result" : [var for r in results for var in r.get_variable_result]}

        return result

    
    async def setVariables(self, payload):

        max_set_messages = (await self.getVariablesByName(["ItemsPerMessageSetVariables"]))["ItemsPerMessageSetVariables"]

        results = await self.sendListByChunks(call.SetVariablesPayload, payload, "set_variable_data", int(max_set_messages))
        result = {"set_variable_result" : [var for r in results for var in r.set_variable_result]}
  
        return result
    

    async def requestStartTransaction(self, payload):

        payload = call.RequestStartTransactionPayload(**payload)
        
        if payload.evse_id is not None and payload.evse_id <= 0:
            raise ValueError("evse id must be > 0")

        if payload.charging_profile is not None:
            #F01.FR.08
            if payload.charging_profile["charging_profile_purpose"] != enums.ChargingProfilePurposeType.tx_profile:
                raise ValueError("charging profile needs to be TxProfile")
            #F01.FR.11
            if "transaction_id" in payload.charging_profile and payload.charging_profile["transaction_id"] is not None:
                raise ValueError("Transaction id shall not be set")

            charge_profile_payload = call.SetChargingProfilePayload(evse_id=payload.evse_id, charging_profile=payload.charging_profile)
            charge_profile_payload.charging_profile["transaction_id"] = "will_be_replaced"
            self.verify_charging_profile_structure(charge_profile_payload)             

        #creating an id for the request
        if payload.remote_start_id is None:
            payload.remote_start_id = ChargePoint.new_remoteStartId()

        response = await self.call(payload)

        if response.status == enums.RequestStartStopStatusType.accepted:

            if response.transaction_id is None:
                future = self.loop.create_future()
                self.wait_start_transaction[payload.remote_start_id] = future
                response.transaction_id = await asyncio.wait_for(future, timeout=5)

            #Send to db
            if payload.charging_profile is not None:
                
                payload.charging_profile["transaction_id"] = response.transaction_id
                
                m = {"evse_id": payload.evse_id, "charging_profile":payload.charging_profile}
                message = Rabbit_Message(method="SetChargingProfile", cp_id=self.id, content=m)
                await ChargePoint.broker.ocpp_log(message)

        return response                

    
    async def requestStopTransaction(self, payload):

        request = call.RequestStopTransactionPayload(**payload)
        return await self.call(request)
    

    async def triggerMessage(self, payload):
        request = call.TriggerMessagePayload(**payload)

        if request.requested_message == enums.MessageTriggerType.status_notification and request.evse["connector_id"] == None:
            raise ValueError("Connector ID is required for status_notification")

        return await self.call(request)


    async def getTransactionStatus(self, payload={}, transaction_id=None):

        if transaction_id is not None:
            payload["transaction_id"] = transaction_id
        
        request = call.GetTransactionStatusPayload(**payload)
        return await self.call(request)

    
    def dates_overlap(self, valid_from1, valid_to1, valid_from2, valid_to2):

        valid_from1 = dateutil.parser.parse(valid_from1) if valid_from1 is not None else datetime.now()
        valid_from2 = dateutil.parser.parse(valid_from2) if valid_from2 is not None else datetime.now()
        valid_to1 = dateutil.parser.parse(valid_to1) if valid_to1 is not None else datetime.max
        valid_to2 = dateutil.parser.parse(valid_to2) if valid_to2 is not None else datetime.max

        if valid_from1 <= valid_to2 and valid_to1 >= valid_from2:
            return True
        
        return False
    
    async def charging_profile_assert_no_conflicts(self, payload):
        #check for conflicts in other charging profiles
        #K01.FR.06, K01.FR.39
        #relevant = {"evse_id": payload["evse_id"]}
        #relevant["charging_profile"] = {key: value for key, value in payload["charging_profile"].items() if key in ["id", "stack_level", "charging_profile_purpose", "valid_from", "valid_to"]}
        #message = ChargePoint.broker.build_message("VERIFY_CHARGING_PROFILE_CONFLICTS", self.id, relevant)
        #response = await ChargePoint.broker.send_request_wait_response(message)
        #if len(response["content"]["conflict_ids"]) != 0:
        #    return "profile conflicts with existing profile"

        charging_profile = datatypes.ChargingProfileType(**payload.charging_profile)

        request = {
            "request_id" : ChargePoint.new_requestId(),
            "evse_id" : payload.evse_id,
            "charging_profile" : {
                "charging_profile_purpose":charging_profile.charging_profile_purpose,
                "stack_level":charging_profile.stack_level
            }
        }
        result = await self.getChargingProfiles(request)

        if result["status"] == enums.GetChargingProfileStatusType.accepted:
            for report in result["data"]:
                for report_charging_profile in report["charging_profile"]:
                    report_charging_profile = datatypes.ChargingProfileType(**report_charging_profile)

                    if report_charging_profile.id == charging_profile.id:
                        continue

                    if charging_profile.charging_profile_purpose==enums.ChargingProfilePurposeType.tx_profile:
                        if charging_profile.transaction_id == report_charging_profile.transaction_id:
                            raise ValueError("Already exists conflicting Profile with different ID")

                    else:
                        if self.dates_overlap(charging_profile.valid_from, charging_profile.valid_to, report_charging_profile.valid_from, report_charging_profile.valid_to):
                            raise ValueError("Already exists conflicting Profile with different ID")

    
    def verify_charging_profile_structure(self, payload):
        #DB bug
        if payload.charging_profile["id"] == 0:
            raise ValueError("Charge profile ID cannot be 0")

        for schedule in payload.charging_profile["charging_schedule"]:
            if schedule["id"] == 0:
                raise ValueError("Charge Schedule ID cannot be 0")

        if payload.charging_profile["charging_profile_purpose"] == enums.ChargingProfilePurposeType.tx_profile:
            #K01.FR.03
            if "transaction_id" not in payload.charging_profile or payload.charging_profile["transaction_id"] is None:
                raise ValueError("Tx_profile needs tansaction id")

            #K01.FR.16
            if payload.evse_id == 0:
                raise ValueError("TxProfile SHALL only be be used with evseId >0")
            
        else:
            if "transaction_id" in payload.charging_profile and payload.charging_profile["transaction_id"] is not None:
                raise ValueError("Only tx_profile can have tansaction id")
        
    
    async def setChargingProfile(self, payload):
        #TODO revisit document
        #K01.FR.34, K01.FR.35, K01.FR.38, K01.FR.18, K01.FR.19, K01.FR.20

        request = call.SetChargingProfilePayload(**payload)

        self.verify_charging_profile_structure(request)
        await self.charging_profile_assert_no_conflicts(request)

        #send message to the cp
        response = await self.call(request)

        #send profile to the db
        if response.status == enums.ChargingProfileStatus.accepted:
            message = Rabbit_Message(method="SetChargingProfile", cp_id=self.id, content=payload)
            await ChargePoint.broker.ocpp_log(message)
        
        return response

    
    async def getCompositeSchedule(self, payload):

        request = call.GetCompositeSchedulePayload(**payload)
        return await self.call(request)
    

    async def async_request(self, request):
        if request.request_id is None: 
            request.request_id = ChargePoint.new_requestId()

        response = await self.call(request)
        response = asdict(response)

        if response["status"] == "Accepted":
            future = self.loop.create_future()
            self.multiple_response_requests[request.request_id] = {"ready" : future, "data": []}

            await asyncio.wait_for(future, timeout=5)
            
            response["data"] = self.multiple_response_requests[request.request_id]["data"]
            self.multiple_response_requests.pop(request.request_id)
        
        return response


    async def getBaseReport(self, payload):
        request = call.GetBaseReportPayload(**payload)
        return await self.async_request(request)

    
    async def getChargingProfiles(self, payload):

        request = call.GetChargingProfilesPayload(**payload)

        #K09.FR.03
        if request.evse_id is None and (request.charging_profile is None or all(v is None for v in request.charging_profile.values())):
            raise ValueError("Specify at least 1 field")

        return await self.async_request(request)

    
    async def clearChargingProfile(self, payload):

        #K10.FR.02
        request = call.ClearChargingProfilePayload(**payload)

        if request.charging_profile_id is None and (request.charging_profile_criteria is None or all(v is None for v in request.charging_profile_criteria.values())):
            raise ValueError("Specify at least 1 field")
            
        message = Rabbit_Message(method="clearChargingProfile", cp_id=self.id, content=payload)
        await ChargePoint.broker.ocpp_log(message)

        return await self.call(request)

    
    async def changeAvailability(self, payload):
        request = call.ChangeAvailabilityPayload(**payload)
        return await self.call(request)
    

    async def setVariableMonitoring(self, payload):

        vars = await self.getVariablesByName(["ItemsPerMessageSetVariableMonitoring", "BytesPerMessageSetVariableMonitoring"])

        results = await self.sendListByChunks(call.SetVariableMonitoringPayload, payload, "set_monitoring_data", int(vars["ItemsPerMessageSetVariableMonitoring"]), int(vars["BytesPerMessageSetVariableMonitoring"]))
        result = {"set_monitoring_result" : [var for r in results for var in r.set_monitoring_result]}

        return result
    
    async def clearVariableMonitoring(self, payload):

        vars = await self.getVariablesByName(["ItemsPerMessageClearVariableMonitoring", "BytesPerMessageClearVariableMonitoring"])

        results = await self.sendListByChunks(call.ClearVariableMonitoringPayload, payload, "id", int(vars["ItemsPerMessageClearVariableMonitoring"]), int(vars["BytesPerMessageClearVariableMonitoring"]))
        result = {"clear_monitoring_result" : [var for r in results for var in r.clear_monitoring_result]}

        return result
    

    async def reset(self,payload):
        request = call.ResetPayload(**payload)
        return await self.call(request)

    async def getLocalListVersion(self, payload=None):
        request = call.GetLocalListVersionPayload()
        return await self.call(request)
        
    
    async def send_auhorization_list(self, payload=None):
        """
        Send a new authorization list to the cp

        Asks the DB for the idtokens and authorizes them for this CP
        Sends the ones that are authorized to the CP as the new authorization List
        """

        if payload["update_type"] == enums.UpdateType.full:
            #Get id tokens from DB
            message = Rabbit_Message(method="SELECT", cp_id=self.id, content={"table":"IdToken"})
            response = await ChargePoint.broker.send_request_wait_response(message)
            if response["status"] != "OK":
                raise ValueError("DB ERROR")

            id_tokens = response['content']
        else:
            id_tokens = payload["id_tokens"]

        local_authorization_list=[]
        for id_token in id_tokens:

            auth_data = datatypes.AuthorizationData(id_token=id_token)

            #if add to local list or update_type_full, id_token_info needs to be specified
            if payload["update_type"] == enums.UpdateType.full or payload["operation"] == "Add":
                
                #authorize the id_token
                id_token_info = await self.get_id_token_info({"id_token": id_token})
                auth_data.id_token_info = id_token_info

                #If idtoken is valid for this CP, add it to the list
                if id_token_info["status"] != enums.AuthorizationStatusType.accepted:
                    continue

            local_authorization_list.append(auth_data)
        
        if len(local_authorization_list) == 0:
            return

        #Ask CP current version of the list
        current_version = int((await self.getLocalListVersion()).version_number)

        #Payload of the request
        request = {
            "version_number":current_version+1,
            "update_type":payload["update_type"],
            "local_authorization_list":local_authorization_list
        }

        #D01.FR.11
        vars = await self.getVariablesByName(["ItemsPerMessageSendLocalList", "BytesPerMessageSendLocalList"])

        #Perform request to the CP, dividing into several requests if needed
        return await self.sendListByChunks(call.SendLocalListPayload, 
            request,
            "local_authorization_list",
            int(vars["ItemsPerMessageSendLocalList"]),
            int(vars["BytesPerMessageSendLocalList"]))
    

    async def setDisplayMessage(self, payload):
        request = call.SetDisplayMessagePayload(**payload)
        return await self.call(request)

    async def getDisplayMessages(self, payload):
        request = call.GetDisplayMessagesPayload(**payload)
        return await self.async_request(request)
    
    async def clearDisplayMessage(self, payload):
        request = call.ClearDisplayMessagePayload(**payload)
        return await self.call(request)
    
    async def unlockConnector(self, payload):
        request = call.UnlockConnectorPayload(**payload)
        return await self.call(request)


#######################Funtions staring from the CP Initiative

    @on('BootNotification')
    async def on_BootNotification(self, **kwargs):
        
        #insert timestamp in bootnofification
        kwargs["timestamp"] = datetime.utcnow().isoformat()

        #inform db that new cp has connected
        message = Rabbit_Message(method="BootNotification", cp_id=self.id, content=kwargs)
        await ChargePoint.broker.ocpp_log(message)

        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status=enums.RegistrationStatusType.accepted
        )

    @on('StatusNotification')
    async def on_StatusNotification(self, **kwargs):

        #inform db that new cp has connected
        message = Rabbit_Message(method="StatusNotification", cp_id=self.id, content=kwargs)

        await ChargePoint.broker.ocpp_log(message)
        
        return call_result.StatusNotificationPayload()

    
    @on('MeterValues')
    async def on_MeterValues(self, **kwargs):

        message = Rabbit_Message(method="MeterValues", cp_id=self.id, content=kwargs)
        await ChargePoint.broker.ocpp_log(message)
        return call_result.MeterValuesPayload()

    
    @on('Authorize')
    async def on_Authorize(self, **kwargs):
        
        #authorize id_token
        id_token_info = await self.get_id_token_info(kwargs)
        return call_result.AuthorizePayload(id_token_info=id_token_info)
        
    @on('TransactionEvent')
    async def on_TransactionEvent(self, **kwargs):
        
        message = Rabbit_Message(method="TransactionEvent", cp_id=self.id, content=kwargs)
        await ChargePoint.broker.ocpp_log(message)

        transaction_response = call_result.TransactionEventPayload()

        if "id_token" in kwargs:
            transaction_response.id_token_info = await self.get_id_token_info(kwargs)
        
        if kwargs["trigger_reason"] == enums.TriggerReasonType.remote_start:

            #Transaction was started remotely, signal the transaction id
            if kwargs["transaction_info"]["remote_start_id"] is not None:
                #get the future with key = correlationid
                future = self.wait_start_transaction.pop(kwargs["transaction_info"]["remote_start_id"])
                future.set_result(kwargs["transaction_info"]["transaction_id"])

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
                #TODO pop from out_of_order_transaction
                self.out_of_order_transaction.add(transaction_id)
            else:
                #verify in db if we have all messages
                try:
                    all_messages_received = await self.guarantee_transaction_integrity(transaction_id)
                except ValueError as ve:
                    logging.error("Cannot verify received all transaction messages " + ve.args[0])
                    return

                if not all_messages_received:
                    logging.info("Messages lost for transaction %s", transaction_id)
    

    def received_message_async_request(self, message):
        if message["request_id"] in self.multiple_response_requests:
            
            self.multiple_response_requests[message["request_id"]]["data"].append(message)

            #last message
            if "tbc" not in message or message["tbc"] is None or message["tbc"]==False:
                self.multiple_response_requests[message["request_id"]]["ready"].set_result(True)
    
    @on("ReportChargingProfiles")
    async def on_reportChargingProfiles(self, **kwargs):
        self.received_message_async_request(kwargs)        
        return call_result.ReportChargingProfilesPayload()
    

    @on("NotifyReport")
    async def on_notifyReport(self, **kwargs):
        self.received_message_async_request(kwargs)  
        return call_result.NotifyReportPayload()
    
    @on("NotifyDisplayMessages")
    async def on_NotifyDisplayMessages(self, **kwargs):
        self.received_message_async_request(kwargs)  
        return call_result.NotifyDisplayMessagesPayload()

    @on("NotifyEvent")
    async def on_notifyEvent(self, **kwargs):
        message = Rabbit_Message(method="NotifyEvent", cp_id=self.id, content=kwargs)
        await ChargePoint.broker.ocpp_log(message)
        return call_result.NotifyEventPayload()


    @on('Heartbeat')
    async def on_Heartbeat(self):
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().isoformat()
        )
    
