import asyncio
from rabbit_mq.rabbit_handler import Rabbit_Handler, Topic_Message
import json
from fastapi import HTTPException
from ocpp.v201 import call, call_result, enums, datatypes
from Exceptions.exceptions import ValidationError, OtherError
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

    
    async def send_request(self, method, CP_Id=None, payload=None, destination="Ocpp_Server"):
        message = Topic_Message(method=method, content=payload, cp_id = CP_Id, origin="API", destination=destination)
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
        raise HTTPException(400, detail="Unknown Transaction")


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

        return (await self.send_request("setChargingProfile", cp_id, {"evse_id":evse, "charging_profile" : charging_profile}))