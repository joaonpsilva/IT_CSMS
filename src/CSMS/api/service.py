from rabbit_mq.rabbit_handler import Rabbit_Handler
from rabbit_mq.Rabbit_Message import Topic_Message
import json
from fastapi import HTTPException
from ocpp.v201 import call, call_result, enums, datatypes
from rabbit_mq.exceptions import ValidationError, OtherError
from datetime import datetime, timedelta
import dataclasses

import logging
LOGGER = logging.getLogger("API")

class API_Service:

    def __init__(self):
        self.event_listeners = {}
        self.broker = None

        self.transaction_cache = {}


    async def start(self, rabbit): 
        try:
            self.broker = Rabbit_Handler("API", self.on_event)
            await self.broker.connect(rabbit, receive_requests=False)
        except:
            LOGGER.info("Could not connect to RabbitMq")


    def update_transaction_cache(self, message): 
        
        transaction_id = message.content["transaction_info"]["transaction_id"]
        if transaction_id not in self.transaction_cache:
            self.transaction_cache[transaction_id] = {
                "cp_id": message.cp_id ,
                "evse_id":message.content["evse"]["id"] if "evse" in message.content else None,
                "action": None}

        if message.content["event_type"] == enums.TransactionEventType.ended:
            self.transaction_cache.pop(transaction_id)


    async def on_event(self, message):
        if message.method == "TransactionEvent":
            self.update_transaction_cache(message)

        if message.method in self.event_listeners:
            for event_queue in self.event_listeners[message.method]:
                await event_queue.put(json.dumps(message.content))

    
    async def send_request(self, method, cp_id=None, payload=None, destination="Ocpp_Server"):
        message = Topic_Message(method=method, content=payload, cp_id = cp_id, origin="API", destination=destination)
        try:
            if message.content is not None and destination=="Ocpp_Server" and message.cp_id is None:
                if "transaction_id" in message.content:
                    message.cp_id = (await self.getInfo_by_TransactionId(message.content["transaction_id"]))["cp_id"]

            return await self.broker.send_request_wait_response(message, timeout=35)
        except OtherError as e:
            raise e
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=e.args[0])
        except Exception as e:
            raise HTTPException(status_code=500, detail=e.args[0])
            

    async def getInfo_by_TransactionId(self, transaction_id):

        if transaction_id in self.transaction_cache:
            return self.transaction_cache[transaction_id]
        
        response = await self.send_request("select", payload={"table":"Transaction", "filters": {"transaction_id" : transaction_id}}, destination="SQL_DB")

        if len(response) > 0:
            return response[0]
        raise HTTPException(404, detail="Transaction not found")


    async def setmaxpower(self, transaction_id, max_power):
        
        response = await self.send_request("select", payload={
            "table":"Transaction",
            "filters":{"transaction_id":transaction_id},
            "mode":{"charging_profile":{}}},
            destination="SQL_DB")

        if len(response) == 0:
            raise HTTPException(400, detail="Unknown Transaction")

        cp_id = response[0]["cp_id"] 
        evse=response[0]["evse_id"]
        profiles = response[0]["charging_profile"]

        if len(profiles) > 0:
            most_important_profile = max(profiles, key= lambda x : x["stack_level"])
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
            "charging_schedule" : [{
                "charging_rate_unit" : enums.ChargingRateUnitType.watts,
                "charging_schedule_period" : [{
                    "start_period" : 0,
                    "limit" : max_power,
                }]
            }]
        }

        return await self.send_request("setChargingProfile", cp_id, {"evse_id":evse, "charging_profile" : charging_profile})


    async def send_authList(self, cp_id, update_type, idtokens=None):

        #update is full, retrieve all idtoken info from db
        if update_type=="full":
            update_type = enums.UpdateType.full
        
            idtokens = await self.send_request("select", cp_id=cp_id,
                payload={"table": "IdToken","mode" : {"id_token_info" : {"group_id_token":{}, "evse":{}}}},
                destination="SQL_DB")
        
        local_authorization_list=[]
        for id_token in idtokens:

            
            #if only adding or deleting need to get information regarding specific idtoken
            mode = {}
            if update_type == "add":
                mode = {"id_token_info" : {"group_id_token":{}, "evse":{}}}

            if update_type == "add" or update_type == "delete":
                update_type = enums.UpdateType.differential
        
                response = await self.send_request("select", cp_id=cp_id,
                    payload={"table": "IdToken","filters" : {"id_token" : id_token},"mode" : mode},
                    destination="SQL_DB")
                
                if len(response) == 0:
                    continue

                id_token = response[0]

            if "id_token_info" in id_token and id_token["id_token_info"]:
                id_token_info = id_token.pop("id_token_info")
                id_token_info["evse_id"] = id_token_info.pop("evse")
            else:
                id_token_info = None

            if id_token["id_token"] == "":
                continue

            local_authorization_list.append({"id_token":id_token, "id_token_info":id_token_info})
        
        if len(local_authorization_list) == 0:
            raise HTTPException(400, detail="No valid id tokens were found")
        
        return await self.send_request("sendAuhorizationList", cp_id, {"update_type":update_type, "local_authorization_list":local_authorization_list})


    async def reserve(self, cp_id, evse_id, id_token):
        id_token = await self.send_request("select", cp_id=cp_id,
                    payload={"table": "IdToken","filters" : {"id_token" : id_token}},
                    destination="SQL_DB")
        
        if len(id_token) == 0:
            raise HTTPException(404, detail="Id_Token not found")
        
        request = {
            "evse_id" : evse_id,
            "id_token" : id_token[0],
            #TODO only to utc after add timedeslta
            "expiry_date_time" : (datetime.utcnow() + timedelta(hours=1)).isoformat()  
        }

        return await self.send_request("reserveNow", cp_id, request)
    
    async def cancel_reservation(self, reservation_id):
        reservation = (await self.send_request("select",
                payload={"table": "Reservation", "filters" : {"id" : reservation_id}},
                destination="SQL_DB"))
        
        if len(reservation) == 0:
            raise HTTPException(404, detail="Reservation not found")

        return await self.send_request("cancelReservation", reservation[0]["cp_id"], payload={"reservation_id" : reservation_id})


    async def create_new_IdToken(self, id_token_info):
        id_token_info = dataclasses.asdict(id_token_info)
        id_token_info["cache_expiry_date_time"] = datetime.utcnow() + timedelta(days=365)
        return await self.send_request("create_new_IdToken", payload=id_token_info, destination="SQL_DB")


    async def set_transaction_limits(self, transaction_id, action, power, max_soc, min_soc):

        if action is None and power is None and max_soc is None and min_soc is None:
            raise HTTPException(400, detail="Specify at least one of the fields")

        transaction_info = await self.getInfo_by_TransactionId(transaction_id)
        if "action" not in transaction_info:
            raise HTTPException(404, "No active Transaction with that ID")

        cp_id = transaction_info["cp_id"]
        evse_id = transaction_info["evse_id"]        
        current_action = transaction_info["action"] 

        if action is not None:
            power_map = {"stop": 0, "normal_charge":1, "pause":2, "charge":3, "discharge":4}
            action = power_map[action]

            #Send message to change the v2g_action
            if current_action is None or current_action != action:
                payload ={
                    "vendor_id": "MagnumCap",
                    "message_id": "v2g_action",
                    "data": {
                        #"evse_id": evse_id,
                        "v2g_action": {
                            "action": action
                }}}
                
                response = await self.send_request("dataTransfer", cp_id, payload=payload)
                if response["status"] != enums.DataTransferStatusType.accepted:
                    return response
                
                self.transaction_cache[transaction_id]["action"] = action
        
        if power is not None or min_soc is not None or max_soc is not None:
            #Send message with charging limits
            payload ={
                "vendor_id": "MagnumCap",
                "message_id": "v2g_action",
                "data": {
                    #"evse_id": evse_id,
                    "change_profile": {
                        "power": power,
                        "min_soc": min_soc,
                        "max_soc": max_soc
            }}}

            return await self.send_request("dataTransfer", cp_id, payload=payload)


