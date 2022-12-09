import uvicorn
from fastapi import FastAPI, Depends, Query, Response, status, Request
from api_Rabbit_Handler import API_Rabbit_Handler
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
logging.basicConfig(level=logging.INFO)


app = FastAPI()
broker = None

def choose_status(response):
    try:
        if response["status"] == "OK":
            return status.HTTP_200_OK
        elif response["status"] == "VAL_ERROR":
            return status.HTTP_400_BAD_REQUEST
    except:
        pass

    return status.HTTP_500_INTERNAL_SERVER_ERROR
    

async def send_request(method, CP_Id=None, payload=None, routing_key="request.ocppserver"):
    message = broker.build_message(method, CP_Id, payload)
    response = await broker.send_request_wait_response(message, routing_key=routing_key)
    stat = choose_status(response)
    return response, stat




@app.post("/ChangeAvailability/{CP_Id}", status_code=200)
async def ChangeAvailability(CP_Id: str, payload: payloads.ChangeAvailabilityPayload, r: Response):
    response, stat = await send_request("CHANGE_AVAILABILITY", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/GetVariables/{CP_Id}", status_code=200)
async def GetVariables(CP_Id: str, payload: payloads.GetVariablesPayload, r: Response):
    response, stat = await send_request("GET_VARIABLES", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/SetVariables/{CP_Id}", status_code=200)
async def SetVariables(CP_Id: str, payload: payloads.SetVariablesPayload, r: Response):
    response, stat = await send_request("SET_VARIABLES", CP_Id, payload)
    r.status_code = stat
    return response  


@app.post("/RequestStartTransaction/{CP_Id}", status_code=200)
async def RequestStartTransaction(CP_Id: str, payload: payloads.RequestStartTransaction_Payload, r: Response):
    response, stat = await send_request("REQUEST_START_TRANSACTION", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/RequestStopTransaction/{CP_Id}", status_code=200)
async def RequestStopTransaction(CP_Id: str, payload: call.RequestStopTransactionPayload, r: Response):
    #TODO request stop transaction without cp id input?
    # request stop transaction with remote start id
    response, stat = await send_request("REQUEST_STOP_TRANSACTION", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/TriggerMessage/{CP_Id}", status_code=200)
async def TriggerMessage(CP_Id: str, payload: payloads.TriggerMessagePayload, r: Response):
    response, stat = await send_request("TRIGGER_MESSAGE", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/GetCompositeSchedule/{CP_Id}", status_code=200)
async def GetCompositeSchedule(CP_Id: str, payload: payloads.GetCompositeSchedulePayload, r: Response):
    response, stat = await send_request("GET_COMPOSITE_SCHEDULE", CP_Id, payload)
    r.status_code = stat
    return response
    #TODO make a get 

@app.post("/SetChargingProfile/{CP_Id}", status_code=200)
async def SetChargingProfile(CP_Id: str, payload: payloads.SetChargingProfilePayload, r: Response):
    response, stat = await send_request("SET_CHARGING_PROFILE", CP_Id, payload)
    r.status_code = stat
    return response

@app.post("/GetChargingProfiles/{CP_Id}", status_code=200)
async def GetChargingProfiles(CP_Id: str, payload: payloads.GetChargingProfilesPayload, r: Response):
    response, stat = await send_request("GET_CHARGING_PROFILES", CP_Id, payload)
    r.status_code = stat
    return response
    #TODO make a get 


@app.post("/ClearChargingProfile/{CP_Id}", status_code=200)
async def ClearChargingProfile(CP_Id: str, payload: payloads.ClearChargingProfilePayload, r: Response):
    response, stat = await send_request("CLEAR_CHARGING_PROFILE", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/GetBaseReport/{CP_Id}", status_code=200)
async def GetBaseReport(CP_Id: str, payload: payloads.GetBaseReport_Payload, r: Response):
    response, stat = await send_request("GET_BASE_REPORT", CP_Id, payload)
    r.status_code = stat
    return response
    #TODO make a get


@app.post("/ClearVariableMonitoring/{CP_Id}", status_code=200)
async def ClearVariableMonitoring(CP_Id: str, payload: payloads.ClearVariableMonitoringPayload, r: Response):
    response, stat = await send_request("CLEAR_VARIABLE_MONITORING", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/SetVariableMonitoring/{CP_Id}", status_code=200)
async def SetVariableMonitoring(CP_Id: str, payload: payloads.SetVariableMonitoringPayload, r: Response):
    response, stat = await send_request("SET_VARIABLE_MONITORING", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/Reset/{CP_Id}", status_code=200)
async def Reset(CP_Id: str, payload: payloads.ResetPayload, r: Response):
    response, stat = await send_request("RESET", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/GetTransactionStatus/{CP_Id}", status_code=200)
async def GetTransactionStatus(CP_Id: str, payload: payloads.GetTransactionStatusPayload, r: Response):
    response, stat = await send_request("GET_TRANSACTION_STATUS", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/send_full_authorization_list/{CP_Id}", status_code=200)
async def send_full_authorization_list(CP_Id: str, r: Response):

    payload = {"update_type" : enums.UpdateType.full}
    response, stat = await send_request("SEND_AUTHORIZATION_LIST", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/differential_Auth_List_Add/{CP_Id}", status_code=200)
async def differential_Auth_List_Add(CP_Id: str, payload: List[datatypes.IdTokenType], r: Response):

    payload = {"update_type" : enums.UpdateType.differential, "id_tokens" : payload, "operation" : "Add"}
    response, stat = await send_request("SEND_AUTHORIZATION_LIST", CP_Id, payload)
    r.status_code = stat
    return response

@app.post("/differential_Auth_List_Delete/{CP_Id}", status_code=200)
async def differential_Auth_List_Delete(CP_Id: str, payload: List[datatypes.IdTokenType], r: Response):

    payload = {"update_type" : enums.UpdateType.differential, "id_tokens" : payload, "operation" : "Delete"}
    response, stat = await send_request("SEND_AUTHORIZATION_LIST", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/CRUD/", status_code=200)
async def CRUD(payload: schemas.CRUD_Payload, r: Response):
    response, stat = await send_request(payload.operation, payload=payload, routing_key="request.db.db1")
    r.status_code = stat
    return response

@app.get("/getTransactions")
async def getTransactions(r: Response):
    response, stat = await send_request("SELECT", payload={"table" : schemas.DB_Tables.Transaction}, routing_key="request.db.db1")
    stat = choose_status(response)
    r.status_code = stat
    return response

@app.get("/getTransactions_ById/{transactionId}")
async def getTransactions(transactionId: str, r: Response):
    response, stat = await send_request("SELECT", payload={"table":schemas.DB_Tables.Transaction, "filters":{"transaction_id":transactionId}}, routing_key="request.db.db1")
    stat = choose_status(response)
    r.status_code = stat
    return response


@app.get("/getConnected_ChargePoints/")
async def getConnected_ChargePoints(r: Response):
    response, stat = await send_request("GET_CONNECTED_CPS")
    r.status_code = stat
    return response



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


async def on_event(message: AbstractIncomingMessage):
    if message["method"] in event_listeners:
        for event_queue in event_listeners[message["method"]]:
            await event_queue.put(json.dumps(message))





@app.on_event("startup")
async def main():

    global broker
    broker = API_Rabbit_Handler(on_event)
    await broker.connect()

    
if __name__ == '__main__':
      uvicorn.run(app, host="0.0.0.0", port=8000,loop= 'asyncio')
