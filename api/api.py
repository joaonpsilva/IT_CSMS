import uvicorn
from fastapi import FastAPI, Depends
from api_Rabbit_Handler import API_Rabbit_Handler
from pydantic import BaseModel
from typing import Dict, List, Optional
from ocpp.v201 import call, call_result, enums, datatypes
import payloads

import asyncio

app = FastAPI()
broker = None


@app.post("/SetChargingProfile/{CP_Id}")
async def SetChargingProfile(CP_Id: str, payload: payloads.SetChargingProfilePayload):
    
    message = broker.build_message("SetChargingProfile", CP_Id, payload)


    response = await broker.send_request_wait_response(message, routing_key="request.ocppserver")
    return response



@app.post("/GetVariables/{CP_Id}")
async def GetVariables(CP_Id: str, payload: List[datatypes.GetVariableDataType]):
    
    message = broker.build_message("GET_VARIABLES", CP_Id, {'get_variable_data' : payload})

    response = await broker.send_request_wait_response(message, routing_key="request.ocppserver")
    return response


@app.post("/SetVariables/{CP_Id}")
async def SetVariables(CP_Id: str, payload: List[datatypes.SetVariableDataType]):

    message = broker.build_message("SET_VARIABLES", CP_Id, {'set_variable_data' : payload})

    response = await broker.send_request_wait_response(message, routing_key="request.ocppserver")
    return response  


@app.post("/RequestStartTransaction/{CP_Id}")
async def RequestStartTransaction(CP_Id: str, payload: payloads.RequestStartTransaction_Payload):

    message = broker.build_message("REQUEST_START_TRANSACTION", CP_Id, payload)

    response = await broker.send_request_wait_response(message, routing_key="request.ocppserver")
    return response  

@app.post("/RequestStopTransaction/{CP_Id}")
async def RequestStopTransaction(CP_Id: str, transaction_id: str):
    #TODO request stop transaction without cp id input?
    # request stop transaction with remote start id

    message = broker.build_message("REQUEST_STOP_TRANSACTION", CP_Id, {"transaction_id" : transaction_id})

    response = await broker.send_request_wait_response(message, routing_key="request.ocppserver")
    return response

@app.post("/TriggerMessage/{CP_Id}")
async def TriggerMessage(CP_Id: str, payload: payloads.TriggerMessage_Payload):

    message = broker.build_message("TRIGGER_MESSAGE", CP_Id, payload)

    response = await broker.send_request_wait_response(message, routing_key="request.ocppserver")
    return response  

@app.get("/GetTransactionStatus/{CP_Id}")
async def GetTransactionStatus(CP_Id: str, transactionId: str = None ):
    #TODO request stop transaction without cp id input?

    message = broker.build_message("GET_TRANSACTION_STATUS", CP_Id, {"transaction_id" : transactionId})

    response = await broker.send_request_wait_response(message, routing_key="request.ocppserver")
    return response


@app.on_event("startup")
async def main():

    global broker
    broker = API_Rabbit_Handler()
    await broker.connect()

    
if __name__ == '__main__':
      uvicorn.run(app, host="0.0.0.0", port=8000,loop= 'asyncio')
