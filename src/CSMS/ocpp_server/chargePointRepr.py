from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call, call_result, enums, datatypes
from ocpp.routing import on, after
from CSMS.ocpp_server.variable_definitions import VARIABLES
from datetime import datetime
import asyncio
from dataclasses import asdict
import logging
import dateutil.parser
from sys import getsizeof
import traceback

from rabbit_mq.rabbit_handler import Topic_Message


class ChargePoint(cp):

    broker = None
    request_Id = 0

    def read_variables():
        #TODO read variables (request_Id) from file
        pass

    def new_Id():
        ChargePoint.request_Id += 1
        return ChargePoint.request_Id

    def __init__(self, id, connection, response_timeout=30):
        super().__init__(id, connection, response_timeout)

        self.max_get_messages=None

        self.loop = asyncio.get_running_loop()
        self.out_of_order_transaction = set([])
        self.multiple_response_requests = {}
        self.wait_start_transaction = {}
        self.wait_reservation_evse_id = None
        
        self.is_online = False
        self.change_is_online = None

        self.logger = logging.getLogger(self.id)
        self.logger.setLevel(logging.DEBUG)
        # create console handler with a higher log level
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        # create formatter and add it to the handlers
        formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)
    
    
    async def send_CP_Message(self, method, content={}, **kwargs):
        """Funtion will use the mapping to call the correct function"""
        try:
            #print(getattr(self, "getVariables"))
            return "OK", await getattr(self, method)(**content)
        except ValueError as ve:
            return "VAL_ERROR", ve.args[0]
    
        except AssertionError as e:
            return "OTHER_ERROR" , e.args[0]

        except Exception as e:
            self.logger.error(traceback.format_exc())
            return "ERROR", None
        
    
    async def authorize_idToken(self, id_token, evse_id=None, **kwargs):
        #no auth required
        if id_token["type"] == enums.IdTokenType.no_authorization:
            return {"status" : enums.AuthorizationStatusType.accepted}
        
        try:
            #get info from db
            message = Topic_Message(method="get_IdToken_Info", cp_id=self.id, content={"id_token": id_token},destination="SQL_DB")
            response = await ChargePoint.broker.send_request_wait_response(message)
            id_token =response["content"]["id_token"]
            id_token_info =response["content"]["id_token_info"]

            if id_token is None:
                return {"status" : enums.AuthorizationStatusType.unknown}

            #assert its the same idtoken
            assert(id_token["id_token"] == id_token["id_token"])
            assert(id_token["type"] == id_token["type"])

            #If id token is valid and known, check status
            if not id_token_info.pop("valid"): 
                return {"status" : enums.AuthorizationStatusType.blocked}
            
            id_token_info["status"] = enums.AuthorizationStatusType.accepted

            #check if is allowed to charge at this CP
            if evse_id is not None and evse_id not in id_token_info["evse_id"]:
                id_token_info["status"] =  enums.AuthorizationStatusType.not_at_this_location

            #evse_id needs to be empty if allowed for all charging station
            message = Topic_Message(method="select", cp_id=self.id, content={"table": "EVSE", "filters":{"cp_id" : self.id}}, destination="SQL_DB")
            response = await ChargePoint.broker.send_request_wait_response(message)
            total_evses = len(response["content"])
            if total_evses == len(id_token_info["evse_id"]):
                id_token_info["evse_id"] = []
            
            #expired
            if id_token_info["cache_expiry_date_time"] != None and id_token_info["cache_expiry_date_time"] < datetime.utcnow().isoformat():
                id_token_info["status"] = enums.AuthorizationStatusType.expired
            
            
            return id_token_info
            
        except:
            self.logger.error(traceback.format_exc())
            return {"status" : enums.AuthorizationStatusType.invalid}



    async def guarantee_transaction_integrity(self, transaction_id):

        message = Topic_Message(method="verify_received_all_transaction", cp_id=self.id, content={"transaction_id" : transaction_id}, destination="SQL_DB")
        response = await ChargePoint.broker.send_request_wait_response(message)

        if response["status"] == "OK":

            if response["content"]["status"] == "OK":
                return True
            self.logger.info("DB could not identify transaction")
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
            response = await self.call(request)
            

            if response.get_variable_result[0]["attribute_status"] == enums.GetVariableStatusType.accepted:
                self.max_get_messages = int(response.get_variable_result[0]["attribute_value"])
            else:
                #if no response assume high number
                self.max_get_messages = 9999

            self.logger.info("Max number of getvariables supported is %d", self.max_get_messages)

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

        max_items = int(max_items) if max_items else None
        max_bytes = int(max_bytes) if max_bytes else None
        
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


        return {request: result['attribute_value'] if result['attribute_status'] == enums.GetVariableStatusType.accepted else None
            for request, result in zip(variables, results["get_variable_result"]) 
            }
        

#######################Functions starting from CSMS Initiative


    async def getVariables(self, **payload):
        """Funtion initiated by the csms to get variables"""

        max_get_messages = await self.get_max_get_messages()

        results = await self.sendListByChunks(call.GetVariablesPayload, payload, "get_variable_data", max_get_messages)
        result = {"get_variable_result" : [var for r in results for var in r.get_variable_result]}

        return result

    
    async def setVariables(self, **payload):

        max_set_messages = (await self.getVariablesByName(["ItemsPerMessageSetVariables"]))["ItemsPerMessageSetVariables"]

        results = await self.sendListByChunks(call.SetVariablesPayload, payload, "set_variable_data", max_set_messages)
        result = {"set_variable_result" : [var for r in results for var in r.set_variable_result]}
  
        return result
    

    async def requestStartTransaction(self, **payload):

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


        #creating an id for the request
        if payload.remote_start_id is None:
            payload.remote_start_id = ChargePoint.new_Id()

        response = await self.call(payload)

        if response.status == enums.RequestStartStopStatusType.accepted:

            if response.transaction_id is None:
                future = self.loop.create_future()
                self.wait_start_transaction[payload.remote_start_id] = future
                response.transaction_id = await asyncio.wait_for(future, timeout=5)

            #TODO REDO THIS Send to db

        return response                

    
    async def requestStopTransaction(self, **payload):

        request = call.RequestStopTransactionPayload(**payload)
        return await self.call(request)
    

    async def triggerMessage(self, **payload):
        request = call.TriggerMessagePayload(**payload)

        if request.requested_message == enums.MessageTriggerType.status_notification and request.evse["connector_id"] == None:
            raise ValueError("Connector ID is required for status_notification")

        return await self.call(request)


    async def getTransactionStatus(self, transaction_id=None, **payload):

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
    
    async def charging_profile_assert_no_conflicts(self, evse_id, charging_profile):
        #check for conflicts in other charging profiles

        request = {
            "evse_id" : evse_id,
            "charging_profile_purpose":charging_profile["charging_profile_purpose"],
            "stack_level":charging_profile["stack_level"]
        }

        message = Topic_Message(method="get_charging_profiles", cp_id=self.id, content=request, destination="SQL_DB")
        result = await ChargePoint.broker.send_request_wait_response(message)


        if result["status"] == "OK":
            for report_charging_profile in result["content"]:
                report_charging_profile = datatypes.ChargingProfileType(**report_charging_profile)

                if "id" in charging_profile and report_charging_profile.id == charging_profile["id"]:
                    continue

                if charging_profile["charging_profile_purpose"] == enums.ChargingProfilePurposeType.tx_profile:
                    if charging_profile["transaction_id"] == report_charging_profile.transaction_id:
                        raise ValueError("Already exists conflicting Profile with different ID")

                else:
                    if self.dates_overlap(charging_profile["valid_from"], charging_profile["valid_to"], report_charging_profile.valid_from, report_charging_profile.valid_to):
                        raise ValueError("Already exists conflicting Profile with different ID")
        else:
            raise AssertionError("Cannot reach DB")

    
    def verify_charging_profile_structure(self, payload):

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
        
    
    async def setChargingProfile(self, **payload):
        #TODO revisit document
        #K01.FR.34, K01.FR.35, K01.FR.38, K01.FR.18, K01.FR.19, K01.FR.20

        request = call.SetChargingProfilePayload(**payload)

        self.verify_charging_profile_structure(request)
        await self.charging_profile_assert_no_conflicts(request.evse_id, request.charging_profile)

        #assume that if either schedule and profile both know id or neither does
        in_db=False
        if request.charging_profile["id"] is None:
            #need to create the profile on the db now
            #need to choose an id for the profile
            #waiting for approval may result in duplicate ids
            
            message = Topic_Message(method="create_Charging_profile", cp_id=self.id, content=request.__dict__, destination="SQL_DB")
            response = await ChargePoint.broker.send_request_wait_response(message)
            assert response["status"] == "OK", "DB comunication failed"
            in_db=True
            request.charging_profile = response["content"]

        #send message to the cp
        response = await self.call(request)
        if response.status == enums.ChargingProfileStatus.accepted:
            if not in_db:
                message = Topic_Message(method="create_Charging_profile", cp_id=self.id, content=request.__dict__, destination="SQL_DB")
                response = await ChargePoint.broker.send_request_wait_response(message)
        else:
            if in_db:
                #if profile is not accepted remove it from the db
                message = Topic_Message(method="remove", cp_id=self.id, content={"table":"ChargingProfile", "filters":{"id":request.charging_profile["id"]}}, destination="SQL_DB")
                await ChargePoint.broker.send_request_wait_response(message)
        
        return response

    
    async def getCompositeSchedule(self, **payload):

        request = call.GetCompositeSchedulePayload(**payload)
        return await self.call(request)
    

    async def async_request(self, request):

        response = await self.call(request)
        response = asdict(response)

        if response["status"] == "Accepted":
            future = self.loop.create_future()
            self.multiple_response_requests[request.request_id] = {"ready" : future, "data": []}

            await asyncio.wait_for(future, timeout=10)
            
            response["data"] = self.multiple_response_requests[request.request_id]["data"]
            self.multiple_response_requests.pop(request.request_id)
        
        return response


    async def getBaseReport(self, **payload):
        if "request_id" not in payload or payload["request_id"] is None:
            payload["request_id"] = ChargePoint.new_Id()

        request = call.GetBaseReportPayload(**payload)
        return await self.async_request(request)

    
    async def getChargingProfiles(self, **payload):

        if "request_id" not in payload or payload["request_id"] is None:
            payload["request_id"] = ChargePoint.new_Id()
        
        request = call.GetChargingProfilesPayload(**payload)

        #K09.FR.03
        if request.evse_id is None and (request.charging_profile is None or all(v is None for v in request.charging_profile.values())):
            raise ValueError("Specify at least 1 field")

        return await self.async_request(request)


    async def new_external_profiles(self):
        request = {"charging_profile" : {"charging_profile_purpose":enums.ChargingProfilePurposeType.charging_station_external_constraints}}    
        reports = await self.getChargingProfiles(**request)

        #delete current external profiles
        message = Topic_Message(method="remove", cp_id=self.id, content={"table":"ChargingProfile", 
                        "filters":{"charging_profile_purpose":enums.ChargingProfilePurposeType.charging_station_external_constraints}},
                        destination="SQL_DB")
        response = await ChargePoint.broker.send_request_wait_response(message)

        #add new profiles
        for r in reports["data"]:
            for profile in r["charging_profile"]:
                message = Topic_Message(method="create_Charging_profile", cp_id=self.id, content={"evse_id":r["evse_id"], "charging_profile": profile}, destination="SQL_DB")
                response = await ChargePoint.broker.send_request_wait_response(message)


    async def clearChargingProfile(self, **payload):

        #K10.FR.02
        request = call.ClearChargingProfilePayload(**payload)

        if request.charging_profile_id is None and (request.charging_profile_criteria is None or all(v is None for v in request.charging_profile_criteria.values())):
            raise ValueError("Specify at least 1 field")
            
        message = Topic_Message(method="clearChargingProfile", cp_id=self.id, content=payload)
        await ChargePoint.broker.ocpp_log(message)

        return await self.call(request)

    
    async def changeAvailability(self, **payload):
        request = call.ChangeAvailabilityPayload(**payload)
        return await self.call(request)
    

    async def setVariableMonitoring(self, **payload):

        vars = await self.getVariablesByName(["ItemsPerMessageSetVariableMonitoring", "BytesPerMessageSetVariableMonitoring"])

        results = await self.sendListByChunks(call.SetVariableMonitoringPayload, payload, "set_monitoring_data", vars["ItemsPerMessageSetVariableMonitoring"], vars["BytesPerMessageSetVariableMonitoring"])
        result = {"set_monitoring_result" : [var for r in results for var in r.set_monitoring_result]}

        return result

    
    async def clearVariableMonitoring(self, **payload):

        vars = await self.getVariablesByName(["ItemsPerMessageClearVariableMonitoring", "BytesPerMessageClearVariableMonitoring"])

        results = await self.sendListByChunks(call.ClearVariableMonitoringPayload, payload, "id", vars["ItemsPerMessageClearVariableMonitoring"], vars["BytesPerMessageClearVariableMonitoring"])
        result = {"clear_monitoring_result" : [var for r in results for var in r.clear_monitoring_result]}

        return result
    

    async def reset(self, **payload):
        request = call.ResetPayload(**payload)
        return await self.call(request)

    async def getLocalListVersion(self, **payload):
        request = call.GetLocalListVersionPayload()
        return await self.call(request)
        
    
    async def send_auhorization_list(self, **payload):
        """
        Send a new authorization list to the cp

        Asks the DB for the idtokens and authorizes them for this CP
        Sends the ones that are authorized to the CP as the new authorization List
        """

        if payload["update_type"] == enums.UpdateType.full:
            #Get id tokens from DB
            message = Topic_Message(method="select", cp_id=self.id, content={"table":"IdToken"}, destination="SQL_DB")
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
                id_token_info = await self.authorize_idToken(id_token)
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
            vars["ItemsPerMessageSendLocalList"],
            vars["BytesPerMessageSendLocalList"])
    

    async def setDisplayMessage(self, **payload):
        request = call.SetDisplayMessagePayload(**payload)
        return await self.call(request)

    async def getDisplayMessages(self, **payload):
        if "request_id" not in payload or payload["request_id"] is None:
            payload["request_id"] = ChargePoint.new_Id()

        request = call.GetDisplayMessagesPayload(**payload)
        return await self.async_request(request)
    
    async def clearDisplayMessage(self, **payload):
        request = call.ClearDisplayMessagePayload(**payload)
        return await self.call(request)
    
    async def unlockConnector(self, **payload):
        request = call.UnlockConnectorPayload(**payload)
        return await self.call(request)

    
    async def wait_for_evse(self, id):
        try:
            self.wait_reservation_evse_id = self.loop.create_future()
            evse_id = await asyncio.wait_for(self.wait_reservation_evse_id, timeout=20)
            message = Topic_Message(method="update", cp_id=self.id, content={"table":"Reservation", "filters":{"id":id}, "values":{"evse_id":evse_id}}, destination="SQL_DB")
            response = await ChargePoint.broker.send_request_wait_response(message)
        except:
            pass


    async def reserveNow(self, **payload):
        request = call.ReserveNowPayload(**payload)
        request.id = ChargePoint.new_Id()
            
        response = await self.call(request)

        if response.status == enums.ReserveNowStatusType.accepted:
            if request.evse_id is None:
                self.loop.create_task(self.wait_for_evse(request.id))

            message = Topic_Message(method="new_Reservation", cp_id=self.id, content=request.__dict__, destination="SQL_DB")
            response = await ChargePoint.broker.send_request_wait_response(message)
                    
        return response
    

    async def change_profile_transaction(self, transaction_id, schedule):
        
        message = Topic_Message(method="select", cp_id=self.id, content={"table":"Transaction", "filters":{"transaction_id":transaction_id}}, destination="SQL_DB")
        response = await ChargePoint.broker.send_request_wait_response(message)
        assert response["status"] == "OK", "DB comunication failed"
        evse=response["content"][0]["evse_id"]

        message = Topic_Message(method="select", cp_id=self.id, content={"table":"ChargingProfile", "filters":{"transaction_id":transaction_id}}, destination="SQL_DB")
        response = await ChargePoint.broker.send_request_wait_response(message)
        assert response["status"] == "OK", "DB comunication failed"

        if len(response["content"]) > 0:
            most_important_profile = max(response["content"], key= lambda x : x["stack_level"])
            id = most_important_profile["id"]
            stack_level = most_important_profile["stack_level"]
        else:
            id = None
            stack_level = 0

        charging_profile = {
            "id" : id,
            "stack_level" : stack_level,
            "charging_profile_purpose" : enums.ChargingProfilePurposeType.tx_profile,
            "charging_profile_kind" : enums.ChargingProfileKindType.relative,
            "transaction_id" : transaction_id,
            "charging_schedule" : schedule
        }

        await self.setChargingProfile(**{"evse_id":evse, "charging_profile" : charging_profile})


    async def setmaxpower(self, transaction_id, max_power):

        charging_schedule = [{
            "charging_rate_unit" : enums.ChargingRateUnitType.watts,
            "charging_schedule_period" : [{
                "start_period" : 0,
                "limit" : max_power,
            }]
        }]

        await self.change_profile_transaction(transaction_id, charging_schedule)
        

#######################Funtions staring from the CP Initiative

    @on('BootNotification')
    async def on_BootNotification(self, **kwargs):
        
        #insert timestamp in bootnofification
        kwargs["timestamp"] = datetime.utcnow().isoformat()

        #inform db that new cp has connected
        message = Topic_Message(method="BootNotification", cp_id=self.id, content=kwargs)
        await ChargePoint.broker.ocpp_log(message)

        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=30,
            status=enums.RegistrationStatusType.accepted
        )


    @after("BootNotification")
    async def after_BootNotification(self, **kwargs):
        await self.new_external_profiles()


    @on('StatusNotification')
    async def on_StatusNotification(self, **kwargs):

        #inform db that new cp has connected
        message = Topic_Message(method="StatusNotification", cp_id=self.id, content=kwargs)
        await ChargePoint.broker.ocpp_log(message)
        
        return call_result.StatusNotificationPayload()
    
    @after('StatusNotification')
    async def after_StatusNotification(self, connector_status, evse_id, **kwargs):
        if connector_status == enums.ConnectorStatusType.reserved and self.wait_reservation_evse_id is not None:
            try:
                self.wait_reservation_evse_id.set_result(evse_id)
            except:
                pass


    @on('MeterValues')
    async def on_MeterValues(self, **kwargs):

        message = Topic_Message(method="MeterValues", cp_id=self.id, content=kwargs)
        await ChargePoint.broker.ocpp_log(message)
        return call_result.MeterValuesPayload()

    
    @on('Authorize')
    async def on_Authorize(self, **kwargs):

        message = Topic_Message(method="Authorize", cp_id=self.id, content=kwargs)
        await ChargePoint.broker.ocpp_log(message)
        
        #authorize id_token
        id_token_info = await self.authorize_idToken(**kwargs)
        return call_result.AuthorizePayload(id_token_info=id_token_info)
        
    @on('TransactionEvent')
    async def on_TransactionEvent(self, **kwargs):
        
        message = Topic_Message(method="TransactionEvent", cp_id=self.id, content=kwargs)
        await ChargePoint.broker.ocpp_log(message)

        transaction_response = call_result.TransactionEventPayload()

        if "id_token" in kwargs:
            transaction_response.id_token_info = await self.authorize_idToken(**kwargs)

        if kwargs["event_type"] == enums.TransactionEventType.ended:
            #Payment (show total cost)
            pass

        
        return transaction_response
    
    @after('TransactionEvent')
    async def after_TransactionEvent(self, transaction_info, event_type,trigger_reason,reservation_id=None, **kwargs):
        transaction_id =  transaction_info["transaction_id"]

        if trigger_reason == enums.TriggerReasonType.remote_start:

            #Transaction was started remotely, signal the transaction id
            if transaction_info["remote_start_id"] is not None:
                #get the future with key = correlationid
                future = self.wait_start_transaction.pop(transaction_info["remote_start_id"])
                future.set_result(transaction_info["transaction_id"])
        

        if event_type == enums.TransactionEventType.started and reservation_id is not None:
            #delete reservation
            message = Topic_Message(method="remove", cp_id=self.id, content={"table": "Reservation", "filters":{"id":reservation_id}},destination="SQL_DB")
            response = await ChargePoint.broker.send_request_wait_response(message)
        

        if event_type == enums.TransactionEventType.ended:
            #delete charging profile
            message = Topic_Message(method="remove", cp_id=self.id, content={"table": "ChargingProfile", "filters":{"transaction_id":transaction_info["transaction_id"]}},destination="SQL_DB")
            response = await ChargePoint.broker.send_request_wait_response(message)


        if event_type == enums.TransactionEventType.ended or transaction_id in self.out_of_order_transaction:
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
                    self.logger.error("Cannot verify received all transaction messages " + ve.args[0])
                    return

                if not all_messages_received:
                    self.logger.info("Messages lost for transaction %s", transaction_id)
    

    def received_message_async_request(self, message):
        if message["request_id"] in self.multiple_response_requests:
            
            self.multiple_response_requests[message["request_id"]]["data"].append(message)

            #last message
            if "tbc" not in message or message["tbc"] is None or message["tbc"]==False:
                self.multiple_response_requests[message["request_id"]]["ready"].set_result(True)
    
    @on("ReportChargingProfiles")
    async def on_reportChargingProfiles(self, **kwargs):
        message = Topic_Message(method="ReportChargingProfiles", cp_id=self.id, content=kwargs)
        await ChargePoint.broker.ocpp_log(message)

        self.received_message_async_request(kwargs)        
        return call_result.ReportChargingProfilesPayload()
    

    @on("NotifyReport")
    async def on_notifyReport(self, **kwargs):
        message = Topic_Message(method="NotifyReport", cp_id=self.id, content=kwargs)
        await ChargePoint.broker.ocpp_log(message)

        self.received_message_async_request(kwargs)  
        return call_result.NotifyReportPayload()
    
    @on("NotifyDisplayMessages")
    async def on_NotifyDisplayMessages(self, **kwargs):
        message = Topic_Message(method="NotifyDisplayMessages", cp_id=self.id, content=kwargs)
        await ChargePoint.broker.ocpp_log(message)

        self.received_message_async_request(kwargs)  
        return call_result.NotifyDisplayMessagesPayload()

    @on("NotifyEvent")
    async def on_notifyEvent(self, **kwargs):
        message = Topic_Message(method="NotifyEvent", cp_id=self.id, content=kwargs)
        await ChargePoint.broker.ocpp_log(message)
        return call_result.NotifyEventPayload()


    @on("NotifyChargingLimit")
    async def on_NotifyChargingLimit(self, **kwargs):
        return call_result.NotifyChargingLimitPayload()
    @after("NotifyChargingLimit")
    async def after_NotifyChargingLimit(self, **kwargs):
        await self.new_external_profiles()


    @on('Heartbeat')
    async def on_Heartbeat(self):
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().isoformat()
        )
    @after('Heartbeat')
    async def after_Heartbeat(self):
        if self.is_online:
            self.change_is_online.cancel()
        else:
            await self.set_on_off(True)
        
        try:
            self.change_is_online = asyncio.create_task(self.set_on_off(False, wait=40)) 
        except asyncio.CancelledError:
            pass


    async def set_on_off(self, on, wait=0):
        #couroutine might be cancelled
        await asyncio.sleep(wait)

        if not self.is_online == on: 
            self.is_online = on
            message = Topic_Message(method="update", cp_id=self.id, content={"table":"Charge_Point", "filters" : {"cp_id" : self.id}, "values":{"is_online":self.is_online}})            
            await ChargePoint.broker.ocpp_log(message)


    
