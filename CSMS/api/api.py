import uvicorn
from fastapi import FastAPI, Depends, Query, Response, status, Request, HTTPException

import sys
from os import path
sys.path.append( path.dirname(path.dirname( path.dirname( path.abspath(__file__) ) ) ))
from rabbit_handler import Rabbit_Handler, Topic_Message

from pydantic import BaseModel
from typing import Dict, List, Optional
from ocpp.v201 import call, call_result, enums
import datatypes
import payloads
import schemas
from aio_pika.abc import AbstractIncomingMessage
import asyncio
import logging
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import json
import argparse
import datetime

parser = argparse.ArgumentParser()
parser.add_argument("-p", type=int, default = 8000, help="OCPP server port")
parser.add_argument("-rb", type=str, default = "amqp://guest:guest@localhost/", help="RabbitMq")
args = parser.parse_args()

LOGGER = logging.getLogger("API")
LOGGER.setLevel(logging.DEBUG)

# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

LOGGER.addHandler(ch)


app = FastAPI()
broker = None

def check_status(response):
    if response["status"] == "OK":
        return
    elif response["status"] == "VAL_ERROR":
        raise HTTPException(status_code=400, detail=response["content"])
    elif response["status"] == "ERROR":
        raise HTTPException(status_code=500)

    
async def send_request(method, CP_Id=None, payload=None, destination="Ocpp_Server"):
    message = Topic_Message(method=method, content=payload,cp_id = CP_Id, origin="API", destination=destination)
    try:
        response = await broker.send_request_wait_response(message)
    except TimeoutError:
        response = {"status":"ERROR", "content": None}
    
    check_status(response)
    return response

##################################################################

@app.post("/register", status_code=201)
async def register(email: str, password:str, full_name:str, status:str, cust_id:int):
    values = {"email": email, "password":password, "full_name":full_name, "status":status, "cust_id":cust_id}
    response = await send_request("register", payload=values, destination="SQL_DB")
    return response["content"]


@app.get("/login", status_code=200)
async def login(email: str, password:str):
    response = await send_request("login", payload={"email": email, "password":password}, destination="SQL_DB")

    if response["status"] == "OTHER_ERROR":
        raise HTTPException(401, detail=response["content"])

    return response["content"]


@app.get("/users", status_code=200)
async def getUsers():
    response = await send_request("select", payload={"table": "User"}, destination="SQL_DB")
    return response["content"]

@app.get("/users/{email}", status_code=200)
async def get_user_byEmail(email:str):
    response = await send_request("select", payload={"table": "User", "filters":{"email":email}}, destination="SQL_DB")
    return response["content"]


@app.get("/transactions", status_code=200)
async def getTransactions(transaction_id:str):
    response = await send_request("select", payload={"table": "Transaction", "filters":{"transaction_id":transaction_id}}, destination="SQL_DB")
    return response["content"]

@app.get("/transactions/open/{id_token}", status_code=200)
async def getOpenTransactionsByIdToken(id_token:str):
    response = await send_request("get_IdToken_Transactions", payload={"id_token": id_token}, destination="SQL_DB")
    return response["content"]


@app.get("/transactions/{id_token}/{date}", status_code=200)
async def getOpenTransactionsByIdToken(id_token:str, date: datetime.datetime):
    response = await send_request("get_Transactions_byDate", payload={"id_token": id_token, "date":date}, destination="SQL_DB")
    return response["content"]


@app.get("/charge/start", status_code=200)
async def charge_start(id_tag: str, evse_id: int, cp_id:str):
    payload = payloads.RequestStartTransactionPayload(
        id_token=datatypes.IdTokenType(id_token=id_tag, type=enums.IdTokenType.iso14443),
        evse_id=evse_id
    )
    response = await send_request("requestStartTransaction", CP_Id=cp_id, payload=payload)
    return response["content"]


@app.get("/charge/stop", status_code=200)
async def charge_stop(transaction_id: str):
    payload = payloads.RequestStopTransactionPayload(transaction_id)
    response = await send_request("requestStopTransaction", payload=payload)
    return response["content"]


@app.get("/setmaxpower", status_code=200)
async def setmaxpower(transaction_id: str, max_power: int):
    payload = {"transaction_id": transaction_id, "max_power":max_power}
    response = await send_request("setmaxpower", payload=payload)
    return response["content"]



@app.get("/stations", status_code=200)
async def stations():
    response = await send_request("select", payload={"table": "Charge_Point"}, destination="SQL_DB")
    return response["content"]


@app.get("/stations/{CP_Id}", status_code=200)
async def getStationById(CP_Id : str):
    mode = {"relationships":{"evse":{"describe":False, "relationships":{"connector":{}}}}}
    response = await send_request("select", payload={"table": "Charge_Point", "filters":{"cp_id":CP_Id}, "mode":mode}, destination="SQL_DB")
    return response["content"]





@app.post("/ChangeAvailability/{CP_Id}", status_code=200)
async def ChangeAvailability(CP_Id: str, payload: payloads.ChangeAvailabilityPayload):
    response = await send_request("changeAvailability", CP_Id, payload)
    return response["content"]

@app.post("/UnlockConnector/{CP_Id}", status_code=200)
async def UnlockConnector(CP_Id: str, payload: payloads.UnlockConnectorPayload):
    response = await send_request("unlockConnector", CP_Id, payload)
    return response["content"]


@app.post("/GetVariables/{CP_Id}", status_code=200)
async def GetVariables(CP_Id: str, payload: payloads.GetVariablesPayload):
    response = await send_request("getVariables", CP_Id, payload)
    return response["content"]


@app.post("/SetVariables/{CP_Id}", status_code=200)
async def SetVariables(CP_Id: str, payload: payloads.SetVariablesPayload):
    response = await send_request("setVariables", CP_Id, payload)
    return response["content"]  


@app.post("/RequestStartTransaction/{CP_Id}", status_code=200)
async def RequestStartTransaction(CP_Id: str, payload: payloads.RequestStartTransactionPayload):
    response = await send_request("requestStartTransaction", CP_Id, payload)
    return response["content"]


@app.post("/RequestStopTransaction/{CP_Id}", status_code=200)
async def RequestStopTransaction(CP_Id: str, payload: call.RequestStopTransactionPayload):
    #TODO request stop transaction without cp id input?
    # request stop transaction with remote start id
    response = await send_request("requestStopTransaction", CP_Id, payload)
    return response["content"]


@app.post("/TriggerMessage/{CP_Id}", status_code=200)
async def TriggerMessage(CP_Id: str, payload: payloads.TriggerMessagePayload):
    response = await send_request("triggerMessage", CP_Id, payload)
    return response["content"]


@app.post("/GetCompositeSchedule/{CP_Id}", status_code=200)
async def GetCompositeSchedule(CP_Id: str, payload: payloads.GetCompositeSchedulePayload):
    response = await send_request("getCompositeSchedule", CP_Id, payload)
    return response["content"]
    #TODO make a get 

@app.post("/SetChargingProfile/{CP_Id}", status_code=200)
async def SetChargingProfile(CP_Id: str, payload: payloads.SetChargingProfilePayload):
    response = await send_request("setChargingProfile", CP_Id, payload)

    if response["status"] != "OK":
        raise HTTPException(500,response["content"] )
    return response["content"]

@app.post("/GetChargingProfiles/{CP_Id}", status_code=200)
async def GetChargingProfiles(CP_Id: str, payload: payloads.GetChargingProfilesPayload):
    response = await send_request("getChargingProfiles", CP_Id, payload)
    return response["content"]
    #TODO make a get 


@app.post("/ClearChargingProfile/{CP_Id}", status_code=200)
async def ClearChargingProfile(CP_Id: str, payload: payloads.ClearChargingProfilePayload):
    response = await send_request("clearChargingProfile", CP_Id, payload)
    return response["content"]


@app.post("/GetBaseReport/{CP_Id}", status_code=200)
async def GetBaseReport(CP_Id: str, payload: payloads.GetBaseReportPayload):
    response = await send_request("getBaseReport", CP_Id, payload)
    return response["content"]
    #TODO make a get


@app.post("/ClearVariableMonitoring/{CP_Id}", status_code=200)
async def ClearVariableMonitoring(CP_Id: str, payload: payloads.ClearVariableMonitoringPayload):
    response = await send_request("clearVariableMonitoring", CP_Id, payload)
    return response["content"]


@app.post("/SetVariableMonitoring/{CP_Id}", status_code=200)
async def SetVariableMonitoring(CP_Id: str, payload: payloads.SetVariableMonitoringPayload):
    response = await send_request("setVariableMonitoring", CP_Id, payload)
    return response["content"]


@app.post("/Reset/{CP_Id}", status_code=200)
async def Reset(CP_Id: str, payload: payloads.ResetPayload):
    response = await send_request("reset", CP_Id, payload)
    return response["content"]


@app.post("/GetTransactionStatus/{CP_Id}", status_code=200)
async def GetTransactionStatus(CP_Id: str, payload: payloads.GetTransactionStatusPayload):
    response = await send_request("getTransactionStatus", CP_Id, payload)
    return response["content"]

@app.get("/GetTransactionStatus", status_code=200)
async def GetTransactionStatus(transaction_id: str):
    response = await send_request("getTransactionStatus", payload={"transaction_id":transaction_id})
    return response["content"]


@app.post("/ReserveNow/{CP_Id}", status_code=200)
async def GetTransactionStatus(CP_Id: str, payload: payloads.ReserveNowPayload):
    response = await send_request("reserveNow", CP_Id, payload)
    return response["content"]



@app.post("/SetDisplayMessage/{CP_Id}", status_code=200)
async def SetDisplayMessage(CP_Id: str, payload: payloads.SetDisplayMessagePayload):
    response = await send_request("setDisplayMessage", CP_Id, payload)
    return response["content"]

@app.post("/GetDisplayMessages/{CP_Id}", status_code=200)
async def GetDisplayMessages(CP_Id: str, payload: payloads.GetDisplayMessagesPayload):
    response = await send_request("getDisplayMessages", CP_Id, payload)
    return response["content"]

@app.post("/ClearDisplayMessage/{CP_Id}", status_code=200)
async def ClearDisplayMessage(CP_Id: str, payload: payloads.ClearDisplayMessagePayload):
    response = await send_request("clearDisplayMessage", CP_Id, payload)
    return response["content"]


@app.post("/send_full_authorization_list/{CP_Id}", status_code=200)
async def send_full_authorization_list(CP_Id: str):
    payload = {"update_type" : enums.UpdateType.full}
    response = await send_request("send_auhorization_list", CP_Id, payload)
    return response["content"]


@app.post("/differential_Auth_List_Add/{CP_Id}", status_code=200)
async def differential_Auth_List_Add(CP_Id: str, payload: List[datatypes.IdTokenType]):
    payload = {"update_type" : enums.UpdateType.differential, "id_tokens" : payload, "operation" : "Add"}
    response = await send_request("send_auhorization_list", CP_Id, payload)
    return response["content"]

@app.post("/differential_Auth_List_Delete/{CP_Id}", status_code=200)
async def differential_Auth_List_Delete(CP_Id: str, payload: List[datatypes.IdTokenType]):
    payload = {"update_type" : enums.UpdateType.differential, "id_tokens" : payload, "operation" : "Delete"}
    response = await send_request("send_auhorization_list", CP_Id, payload)
    return response["content"]


@app.post("/CRUD/", status_code=200)
async def CRUD(payload: schemas.CRUD_Payload):
    response = await send_request(payload.operation, payload=payload, destination="SQL_DB")
    return response["content"]

@app.get("/getTransactions")
async def getTransactions():
    response = await send_request("select", payload={"table" : schemas.DB_Tables.Transaction}, destination="SQL_DB")
    return response["content"]

@app.get("/getTransactions_ById/{transactionId}")
async def getTransactions(transactionId: str):
    response = await send_request("select", payload={"table":schemas.DB_Tables.Transaction, "filters":{"transaction_id":transactionId}}, destination="SQL_DB")
    return response["content"]


@app.get("/getConnected_ChargePoints/")
async def getConnected_ChargePoints():
    response = await send_request("get_connected_cps")
    return response["content"]


event_listeners = {}
@app.get('/stream')
async def message_stream(request: Request, events: List[enums.Action]= Query(
                    [],
                    title="Events")):

    if len(events) == 0:
        return {"status": "VAL_ERROR", "content":"specify at least 1 event"}

    event_queue = asyncio.Queue()

    #put queue to receive events 
    for event in events:
        if event not in event_listeners:
            event_listeners[event] = []
        event_listeners[event].append(event_queue)
    

    async def event_generator():
        while True:
            # If client closes connection, stop sending events
            if await request.is_disconnected():
                #remove queue from listener
                for event in events:
                    event_listeners[event].remove(event_queue)
                break
            
            try:
                #read and yield events as they arrive
                new_event = await event_queue.get()
                yield new_event
                event_queue.task_done()
            except:
                pass
        

    return EventSourceResponse(event_generator())


async def on_event(message):
    if message.method in event_listeners:
        for event_queue in event_listeners[message.method]:
            await event_queue.put(json.dumps(message.content))



@app.on_event("startup")
async def main():

    global broker
    broker = Rabbit_Handler("API", on_event)
    await broker.connect(args.rb, receive_requests=False)

    
if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=args.p,loop= 'asyncio')
