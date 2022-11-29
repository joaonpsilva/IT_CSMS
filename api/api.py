import uvicorn
from fastapi import FastAPI, Depends, Query, Response, status, Request
from api_Rabbit_Handler import API_Rabbit_Handler
from pydantic import BaseModel
from typing import Dict, List, Optional
from ocpp.v201 import call, call_result, enums, datatypes
import payloads
from aio_pika.abc import AbstractIncomingMessage
import asyncio
import logging
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import json
logging.basicConfig(level=logging.INFO)


app = FastAPI()
broker = None

async def send_ocpp_payload(method, CP_Id, payload):
    message = broker.build_message(method, CP_Id, payload)
    response = await broker.send_request_wait_response(message, routing_key="request.ocppserver")

    if response["STATUS"] == "OK":
        stat = status.HTTP_200_OK
    elif response["STATUS"] == "VAL_ERROR":
        stat = status.HTTP_400_BAD_REQUEST
    else:
        stat = status.HTTP_500_INTERNAL_SERVER_ERROR

    return response, stat




@app.post("/ChangeAvailability/{CP_Id}", status_code=200)
async def ChangeAvailability(CP_Id: str, payload: payloads.ChangeAvailabilityPayload, r: Response):
    response, stat = await send_ocpp_payload("CHANGE_AVAILABILITY", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/GetVariables/{CP_Id}", status_code=200)
async def GetVariables(CP_Id: str, payload: List[datatypes.GetVariableDataType], r: Response):
    response, stat = await send_ocpp_payload("GET_VARIABLES", CP_Id, {'get_variable_data' : payload})
    r.status_code = stat
    return response


@app.post("/SetVariables/{CP_Id}", status_code=200)
async def SetVariables(CP_Id: str, payload: List[datatypes.SetVariableDataType], r: Response):
    response, stat = await send_ocpp_payload("SET_VARIABLES", CP_Id, {'set_variable_data' : payload})
    r.status_code = stat
    return response  


@app.post("/RequestStartTransaction/{CP_Id}", status_code=200)
async def RequestStartTransaction(CP_Id: str, payload: payloads.RequestStartTransaction_Payload, r: Response):
    response, stat = await send_ocpp_payload("REQUEST_START_TRANSACTION", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/RequestStopTransaction/{CP_Id}", status_code=200)
async def RequestStopTransaction(CP_Id: str, transaction_id: str, r: Response):
    #TODO request stop transaction without cp id input?
    # request stop transaction with remote start id
    response, stat = await send_ocpp_payload("REQUEST_STOP_TRANSACTION", CP_Id, {"transaction_id" : transaction_id})
    r.status_code = stat
    return response


@app.post("/TriggerMessage/{CP_Id}", status_code=200)
async def TriggerMessage(CP_Id: str, payload: payloads.TriggerMessage_Payload, r: Response):
    response, stat = await send_ocpp_payload("TRIGGER_MESSAGE", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/GetCompositeSchedule/{CP_Id}", status_code=200)
async def GetCompositeSchedule(CP_Id: str, payload: payloads.GetCompositeSchedulePayload, r: Response):
    response, stat = await send_ocpp_payload("GET_COMPOSITE_SCHEDULE", CP_Id, payload)
    r.status_code = stat
    return response
    #TODO make a get 

@app.post("/SetChargingProfile/{CP_Id}", status_code=200)
async def SetChargingProfile(CP_Id: str, payload: payloads.SetChargingProfilePayload, r: Response):
    response, stat = await send_ocpp_payload("SET_CHARGING_PROFILE", CP_Id, payload)
    r.status_code = stat
    return response

@app.post("/GetChargingProfiles/{CP_Id}", status_code=200)
async def GetChargingProfiles(CP_Id: str, payload: payloads.GetChargingProfilesPayload, r: Response):
    response, stat = await send_ocpp_payload("GET_CHARGING_PROFILES", CP_Id, payload)
    r.status_code = stat
    return response
    #TODO make a get 


@app.post("/ClearChargingProfile/{CP_Id}", status_code=200)
async def ClearChargingProfile(CP_Id: str, payload: payloads.ClearChargingProfilePayload, r: Response):
    response, stat = await send_ocpp_payload("CLEAR_CHARGING_PROFILE", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/GetBaseReport/{CP_Id}", status_code=200)
async def GetBaseReport(CP_Id: str, payload: payloads.GetBaseReportPayload, r: Response):
    response, stat = await send_ocpp_payload("GET_BASE_REPORT", CP_Id, payload)
    r.status_code = stat
    return response
    #TODO make a get


@app.post("/ClearVariableMonitoring/{CP_Id}", status_code=200)
async def ClearVariableMonitoring(CP_Id: str, payload: payloads.ClearVariableMonitoringPayload, r: Response):
    response, stat = await send_ocpp_payload("CLEAR_VARIABLE_MONITORING", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/SetVariableMonitoring/{CP_Id}", status_code=200)
async def SetVariableMonitoring(CP_Id: str, payload: payloads.SetVariableMonitoringPayload, r: Response):
    response, stat = await send_ocpp_payload("SET_VARIABLE_MONITORING", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/Reset/{CP_Id}", status_code=200)
async def Reset(CP_Id: str, payload: payloads.ResetPayload, r: Response):
    response, stat = await send_ocpp_payload("RESET", CP_Id, payload)
    r.status_code = stat
    return response


@app.get("/GetTransactionStatus/{CP_Id}", status_code=200)
async def GetTransactionStatus(CP_Id: str,r: Response, transactionId: str = None):
    response, stat = await send_ocpp_payload("GET_TRANSACTION_STATUS", CP_Id, {"transaction_id" : transactionId})
    r.status_code = stat
    return response
    #TODO request stop transaction without cp id input?


event_listeners = {}
@app.get('/stream')
async def message_stream(request: Request, events: List[enums.Action]= Query(
                    [],
                    title="Events")):

    if len(events) == 0:
        return {"STATUS": "VAL_ERROR", "CONTENT":"specify at least 1 event"}

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
    if message["METHOD"] in event_listeners:
        for event_queue in event_listeners[message["METHOD"]]:
            await event_queue.put(json.dumps(message))





@app.on_event("startup")
async def main():

    global broker
    broker = API_Rabbit_Handler(on_event)
    await broker.connect()

    
if __name__ == '__main__':
      uvicorn.run(app, host="0.0.0.0", port=8000,loop= 'asyncio')
