import uvicorn
from fastapi import FastAPI, Depends, Response, status
from api_Rabbit_Handler import API_Rabbit_Handler
from pydantic import BaseModel
from typing import Dict, List, Optional
from ocpp.v201 import call, call_result, enums, datatypes
import payloads

import asyncio

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


@app.post("/SetChargingProfile/{CP_Id}", status_code=200)
async def SetChargingProfile(CP_Id: str, payload: payloads.SetChargingProfilePayload, r: Response):
    response, stat = await send_ocpp_payload("SET_CHARGING_PROFILE", CP_Id, payload)
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


@app.get("/GetTransactionStatus/{CP_Id}", status_code=200)
async def GetTransactionStatus(CP_Id: str,r: Response, transactionId: str = None):
    response, stat = await send_ocpp_payload("GET_TRANSACTION_STATUS", CP_Id, {"transaction_id" : transactionId})
    r.status_code = stat
    return response
    #TODO request stop transaction without cp id input?


@app.on_event("startup")
async def main():

    global broker
    broker = API_Rabbit_Handler()
    await broker.connect()

    
if __name__ == '__main__':
      uvicorn.run(app, host="0.0.0.0", port=8000,loop= 'asyncio')
