from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call, call_result, enums, datatypes
from ocpp.routing import on, after

from datetime import datetime
import asyncio
from dataclasses import asdict
import logging
import dateutil.parser
from sys import getsizeof

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
            "CLEAR_VARIABLE_MONITORING" : self.clearVariableMonitoring
        }

        
        #Variables Cache
        component_DeviceDataCtrlr = datatypes.ComponentType(
            name="DeviceDataCtrlr"
        )
        component_MonitoringCtrlr = datatypes.ComponentType(
            name="MonitoringCtrlr"
        )

        self.variables ={
            "ItemsPerMessageGetVariables" : {
                "component" : component_DeviceDataCtrlr,
                "variable" : datatypes.VariableType(
                    name="ItemsPerMessage",
                    instance="GetVariables"
                )            
            },
            "ItemsPerMessageSetVariables" : {
                "component" : component_DeviceDataCtrlr,
                "variable" : datatypes.VariableType(
                    name="ItemsPerMessage",
                    instance="SetVariables"
                )            
            },
            "BytesPerMessageSetVariableMonitoring" : {
                "component" : component_MonitoringCtrlr,
                "variable" : datatypes.VariableType(
                    name="BytesPerMessage",
                    instance="SetVariableMonitoring"
                )
            },
            "ItemsPerMessageSetVariableMonitoring" : {
                "component" : component_MonitoringCtrlr,
                "variable" : datatypes.VariableType(
                    name="ItemsPerMessage",
                    instance="SetVariableMonitoring"
                )
            },
            "ItemsPerMessageClearVariableMonitoring" : {
                "component" : component_MonitoringCtrlr,
                "variable" : datatypes.VariableType(
                    name="ItemsPerMessage",
                    instance="ClearVariableMonitoring"
                )
            },
            "BytesPerMessageClearVariableMonitoring" : {
                "component" : component_MonitoringCtrlr,
                "variable" : datatypes.VariableType(
                    name="BytesPerMessage",
                    instance="ClearVariableMonitoring"
                )
            }
        }
        self.max_get_messages=None

        self.loop = asyncio.get_running_loop()
        self.out_of_order_transaction = set([])
        self.multiple_response_requests = {}
        self.wait_start_transaction = {}
    
    def api_response(self, status, message):
        return {"STATUS":status, "CONTENT":message}
    
    async def send_CP_Message(self, method, payload):
        """Funtion will use the mapping defined in method_mapping to call the correct function"""
        try:
            return self.api_response("OK", await self.method_mapping[method](payload=payload))
        except ValueError as ve:
            return self.api_response("VAL_ERROR", ve.args[0])

    
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
    

    async def get_max_get_messages(self):
        if self.max_get_messages is None:
            request = call.GetVariablesPayload(get_variable_data=[
                datatypes.GetVariableDataType(
                    component=self.variables["ItemsPerMessageGetVariables"]["component"],
                    variable=self.variables["ItemsPerMessageGetVariables"]["variable"]
                )
            ])
            self.max_get_messages = int((await self.call(request)).get_variable_result[0]["attribute_value"])
            logging.info("Max number of getvariables supported is %d", self.max_get_messages)

        return self.max_get_messages


    async def getVariablesByName(self, variables):
        """
        getvariables by Name. Segment message and do multiple getvariablesRequests to respect cp limits
        ARGS: List of var names (str) or tuple(name, enums.AttributeType)
        RETURNS dict with key name(str) or (name,enums.AttributeType) and value is what was returned in attribute_value
        If variable was not known, it will not be in the return
        """
        max_get_messages = await self.get_max_get_messages()
        requests = []
        results = []

        for variable in variables.copy():
            
            if isinstance(variable, tuple):
                variable_name = variable[0]
                type = variable[1]
            else:
                variable_name = variable
                type = enums.AttributeType.actual
            
            if variable_name in self.variables:
                requests.append(datatypes.GetVariableDataType(
                    component=self.variables[variable_name]["component"],
                    variable=self.variables[variable_name]["variable"],
                    attribute_type=type
                ))
            else:
                variables.remove(variable)

            #max messages can put in get has been reached
            if max_get_messages and len(requests) == max_get_messages:
                results += (await self.getVariables({"get_variable_data":requests})).get_variable_result
                requests=[]
        
        #may there still be some remaining request variables
        if len(requests) > 0:
            results += (await self.getVariables({"get_variable_data":requests})).get_variable_result

        return {request: result['attribute_value'] for request, result in zip(variables, results) 
            if result['attribute_status'] == enums.GetVariableStatusType.accepted}
        

#######################Functions starting from CSMS Initiative


    async def getVariables(self, payload):
        """Funtion initiated by the csms to get variables"""
        request = call.GetVariablesPayload(**payload)

        max_get_messages = await self.get_max_get_messages()
        
        if max_get_messages and len(request.get_variable_data) > max_get_messages:
            raise ValueError("Maximum number of setVariable messages is {}, current is {}".format(max_get_messages, len(request.get_variable_data)))

        return await self.call(request)

    
    async def setVariables(self, payload):
        request = call.SetVariablesPayload(set_variable_data=payload['set_variable_data'])

        vars = await self.getVariablesByName(["ItemsPerMessageSetVariables"])

        #B05.FR.11
        if len(request.set_variable_data) > int(vars["ItemsPerMessageSetVariables"]):
            raise ValueError("Maximum number of setVariable messages is {}, current is {}".format(vars["ItemsPerMessageSetVariables"], len(request.set_variable_data)))
        
        return await self.call(request)
    

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
                message = ChargePoint.broker.build_message("SetChargingProfile", self.id, m)
                await ChargePoint.broker.send_to_DB(message)

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
        #if len(response["CONTENT"]["conflict_ids"]) != 0:
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
            message = ChargePoint.broker.build_message("SetChargingProfile", self.id, payload)
            await ChargePoint.broker.send_to_DB(message)
        
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
            
        message = ChargePoint.broker.build_message("clearChargingProfile", self.id, payload)
        await ChargePoint.broker.send_to_DB(message)

        return await self.call(request)

    
    async def changeAvailability(self, payload):
        request = call.ChangeAvailabilityPayload(**payload)
        return await self.call(request)
    

    async def setVariableMonitoring(self, payload):

        vars = await self.getVariablesByName(["ItemsPerMessageSetVariableMonitoring", "BytesPerMessageSetVariableMonitoring"])
        request = call.SetVariableMonitoringPayload(**payload)

        if len(request.set_monitoring_data) > int(vars["ItemsPerMessageSetVariableMonitoring"]):
            raise ValueError("Maximum number of set monitor messages is {}, current is {}".format(vars["ItemsPerMessageSetVariableMonitoring"], len(request.set_monitoring_data)))
        if getsizeof(request.set_monitoring_data) > int(vars["BytesPerMessageSetVariableMonitoring"]):
            raise ValueError("Maximum number of bytes is {}, current is {}".format(vars["BytesPerMessageSetVariableMonitoring"], getsizeof(request.set_monitoring_data)))

        return await self.call(request) 
    
    async def clearVariableMonitoring(self, payload):

        vars = await self.getVariablesByName(["ItemsPerMessageClearVariableMonitoring", "BytesPerMessageClearVariableMonitoring"])
        request = call.ClearVariableMonitoringPayload(**payload)

        if len(request.id) > int(vars["ItemsPerMessageClearVariableMonitoring"]):
            raise ValueError("Maximum number of clear monitor messages is {}, current is {}".format(vars["ItemsPerMessageClearVariableMonitoring"], len(request.id)))
        if getsizeof(request.id) > int(vars["BytesPerMessageClearVariableMonitoring"]):
            raise ValueError("Maximum number of bytes is {}, current is {}".format(vars["BytesPerMessageClearVariableMonitoring"], getsizeof(request.id)))

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
                all_messages_received = await self.guarantee_transaction_integrity(transaction_id)
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

    @on("NotifyEvent")
    async def on_notifyEvent(self, **kwargs):
        return call_result.NotifyEventPayload()


    @on('Heartbeat')
    async def on_Heartbeat(self):
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().isoformat()
        )
    
