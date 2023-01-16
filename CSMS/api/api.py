import uvicorn
from fastapi import FastAPI, Depends, Query, Response, status, Request
from api_Rabbit_Handler import API_Rabbit_Handler, Rabbit_Message
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

parser = argparse.ArgumentParser()
parser.add_argument("-p", type=int, default = 8000, help="OCPP server port")
parser.add_argument("-rb", type=str, default = "amqp://guest:guest@localhost/", help="RabbitMq")
args = parser.parse_args()

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
    

async def send_request(method, CP_Id=None, payload=None, destination="ocppserver"):
    message = Rabbit_Message(method=method, content=payload,cp_id = CP_Id, origin="api", destination=destination)
    response = await broker.send_request_wait_response(message)
    stat = choose_status(response)
    return response, stat




@app.post("/ChangeAvailability/{CP_Id}", status_code=200)
async def ChangeAvailability(CP_Id: str, payload: payloads.ChangeAvailabilityPayload, r: Response):
    response, stat = await send_request("changeAvailability", CP_Id, payload)
    r.status_code = stat
    return response

@app.post("/UnlockConnector/{CP_Id}", status_code=200)
async def UnlockConnector(CP_Id: str, payload: payloads.UnlockConnectorPayload, r: Response):
    response, stat = await send_request("unlockConnector", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/GetVariables/{CP_Id}", status_code=200)
async def GetVariables(CP_Id: str, payload: payloads.GetVariablesPayload, r: Response):
    response, stat = await send_request("getVariables", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/SetVariables/{CP_Id}", status_code=200)
async def SetVariables(CP_Id: str, payload: payloads.SetVariablesPayload, r: Response):
    response, stat = await send_request("setVariables", CP_Id, payload)
    r.status_code = stat
    return response  


@app.post("/RequestStartTransaction/{CP_Id}", status_code=200)
async def RequestStartTransaction(CP_Id: str, payload: payloads.RequestStartTransaction_Payload, r: Response):
    response, stat = await send_request("requestStartTransaction", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/RequestStopTransaction/{CP_Id}", status_code=200)
async def RequestStopTransaction(CP_Id: str, payload: call.RequestStopTransactionPayload, r: Response):
    #TODO request stop transaction without cp id input?
    # request stop transaction with remote start id
    response, stat = await send_request("requestStopTransaction", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/TriggerMessage/{CP_Id}", status_code=200)
async def TriggerMessage(CP_Id: str, payload: payloads.TriggerMessagePayload, r: Response):
    response, stat = await send_request("triggerMessage", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/GetCompositeSchedule/{CP_Id}", status_code=200)
async def GetCompositeSchedule(CP_Id: str, payload: payloads.GetCompositeSchedulePayload, r: Response):
    response, stat = await send_request("getCompositeSchedule", CP_Id, payload)
    r.status_code = stat
    return response
    #TODO make a get 

@app.post("/SetChargingProfile/{CP_Id}", status_code=200)
async def SetChargingProfile(CP_Id: str, payload: payloads.SetChargingProfilePayload, r: Response):
    response, stat = await send_request("setChargingProfile", CP_Id, payload)
    r.status_code = stat
    return response

@app.post("/GetChargingProfiles/{CP_Id}", status_code=200)
async def GetChargingProfiles(CP_Id: str, payload: payloads.GetChargingProfilesPayload, r: Response):
    response, stat = await send_request("getChargingProfiles", CP_Id, payload)
    r.status_code = stat
    return response
    #TODO make a get 


@app.post("/ClearChargingProfile/{CP_Id}", status_code=200)
async def ClearChargingProfile(CP_Id: str, payload: payloads.ClearChargingProfilePayload, r: Response):
    response, stat = await send_request("clearChargingProfile", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/GetBaseReport/{CP_Id}", status_code=200)
async def GetBaseReport(CP_Id: str, payload: payloads.GetBaseReport_Payload, r: Response):
    response, stat = await send_request("getBaseReport", CP_Id, payload)
    r.status_code = stat
    return response
    #TODO make a get


@app.post("/ClearVariableMonitoring/{CP_Id}", status_code=200)
async def ClearVariableMonitoring(CP_Id: str, payload: payloads.ClearVariableMonitoringPayload, r: Response):
    response, stat = await send_request("clearVariableMonitoring", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/SetVariableMonitoring/{CP_Id}", status_code=200)
async def SetVariableMonitoring(CP_Id: str, payload: payloads.SetVariableMonitoringPayload, r: Response):
    response, stat = await send_request("setVariableMonitoring", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/Reset/{CP_Id}", status_code=200)
async def Reset(CP_Id: str, payload: payloads.ResetPayload, r: Response):
    response, stat = await send_request("reset", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/GetTransactionStatus/{CP_Id}", status_code=200)
async def GetTransactionStatus(CP_Id: str, payload: payloads.GetTransactionStatusPayload, r: Response):
    response, stat = await send_request("getTransactionStatus", CP_Id, payload)
    r.status_code = stat
    return response

@app.get("/GetTransactionStatus", status_code=200)
async def GetTransactionStatus(transaction_id: str, r: Response):
    response, stat = await send_request("getTransactionStatus", payload={"transaction_id":transaction_id})
    r.status_code = stat
    return response



@app.post("/SetDisplayMessage/{CP_Id}", status_code=200)
async def SetDisplayMessage(CP_Id: str, payload: payloads.SetDisplayMessagePayload, r: Response):
    response, stat = await send_request("setDisplayMessage", CP_Id, payload)
    r.status_code = stat
    return response

@app.post("/GetDisplayMessages/{CP_Id}", status_code=200)
async def GetDisplayMessages(CP_Id: str, payload: payloads.GetDisplayMessagesPayload, r: Response):
    response, stat = await send_request("getDisplayMessages", CP_Id, payload)
    r.status_code = stat
    return response

@app.post("/ClearDisplayMessage/{CP_Id}", status_code=200)
async def ClearDisplayMessage(CP_Id: str, payload: payloads.ClearDisplayMessagePayload, r: Response):
    response, stat = await send_request("clearDisplayMessage", CP_Id, payload)
    r.status_code = stat
    return response




@app.post("/send_full_authorization_list/{CP_Id}", status_code=200)
async def send_full_authorization_list(CP_Id: str, r: Response):

    payload = {"update_type" : enums.UpdateType.full}
    response, stat = await send_request("send_auhorization_list", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/differential_Auth_List_Add/{CP_Id}", status_code=200)
async def differential_Auth_List_Add(CP_Id: str, payload: List[datatypes.IdTokenType], r: Response):

    payload = {"update_type" : enums.UpdateType.differential, "id_tokens" : payload, "operation" : "Add"}
    response, stat = await send_request("send_auhorization_list", CP_Id, payload)
    r.status_code = stat
    return response

@app.post("/differential_Auth_List_Delete/{CP_Id}", status_code=200)
async def differential_Auth_List_Delete(CP_Id: str, payload: List[datatypes.IdTokenType], r: Response):

    payload = {"update_type" : enums.UpdateType.differential, "id_tokens" : payload, "operation" : "Delete"}
    response, stat = await send_request("send_auhorization_list", CP_Id, payload)
    r.status_code = stat
    return response


@app.post("/CRUD/", status_code=200)
async def CRUD(payload: schemas.CRUD_Payload, r: Response):
    response, stat = await send_request(payload.operation, payload=payload, destination="db1")
    r.status_code = stat
    return response

@app.get("/getTransactions")
async def getTransactions(r: Response):
    response, stat = await send_request("select", payload={"table" : schemas.DB_Tables.Transaction}, destination="db1")
    stat = choose_status(response)
    r.status_code = stat
    return response

@app.get("/getTransactions_ById/{transactionId}")
async def getTransactions(transactionId: str, r: Response):
    response, stat = await send_request("select", payload={"table":schemas.DB_Tables.Transaction, "filters":{"transaction_id":transactionId}}, destination="db1")
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


async def on_event(message):
    if message.method in event_listeners:
        for event_queue in event_listeners[message.method]:
            await event_queue.put(json.dumps(message.content))



@app.on_event("startup")
async def main():

    global broker
    broker = API_Rabbit_Handler("api", on_event)
    await broker.connect(args.rb)

    
if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=args.p,loop= 'asyncio')
