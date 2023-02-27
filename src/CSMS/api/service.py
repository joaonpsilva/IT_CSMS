import asyncio
from rabbit_mq.rabbit_handler import Rabbit_Handler, Topic_Message
import json
from fastapi import HTTPException
from ocpp.v201 import call, call_result, enums, datatypes
from Exceptions.exceptions import ValidationError, OtherError
from datetime import datetime, timedelta
import dataclasses

import logging
LOGGER = logging.getLogger("API")

class API_Service:

    def __init__(self):
        self.event_listeners = {}
        self.broker = None

    async def start(self, rabbit): 
        try:
            self.broker = Rabbit_Handler("API", self.on_event)
            await self.broker.connect(rabbit, receive_requests=False)
        except:
            LOGGER.info("Could not connect to RabbitMq")
    

    async def on_event(self, message):
        if message.method in self.event_listeners:
            for event_queue in self.event_listeners[message.method]:
                await event_queue.put(json.dumps(message.content))

    
    async def send_request(self, method, cp_id=None, payload=None, destination="Ocpp_Server"):
        message = Topic_Message(method=method, content=payload, cp_id = cp_id, origin="API", destination=destination)
        try:
            if destination=="Ocpp_Server" and message.cp_id is None:
                if "transaction_id" in message.content:
                    message.cp_id = await self.get_cpID_by_TransactionId(message.content["transaction_id"])

            return await self.broker.send_request_wait_response(message)
        except OtherError as e:
            raise e
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=e.args[0])
        except Exception as e:
            raise HTTPException(status_code=500, detail=e.args[0])
            

    async def get_cpID_by_TransactionId(self, transaction_id):
        response = await self.send_request("select", payload={"table":"Transaction", "filters": {"transaction_id" : transaction_id}}, destination="SQL_DB")

        if len(response) > 0:
            return response[0]["cp_id"]
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
            "expiry_date_time" : datetime.utcnow() + timedelta(hours=1)            
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
