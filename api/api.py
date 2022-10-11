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


@app.post("/GetVariables/{CS_Number}")
async def GetVariables(CS_Number: int, payload: List[datatypes.GetVariableDataType]):
    
    message = {
        "CS_ID" : CS_Number,
        "METHOD" : "GET_VARIABLES",
        "PAYLOAD" : {'get_variable_data' : payload}
    }

    response = await broker.send_request(message)
    return response


@app.post("/SetVariables/{CS_Number}")
async def SetVariables(CS_Number: int, payload: List[datatypes.SetVariableDataType]):
    message = {
        "CS_ID" : CS_Number,
        "METHOD" : "SET_VARIABLES",
        "PAYLOAD" : {'set_variable_data' : payload}
    }

    response = await broker.send_request(message)
    return response  


@app.post("/RequestStartTransaction/{CS_Number}")
async def RequestStartTransaction(CS_Number: int, payload: payloads.RequestStartTransaction_Payload):
    message = {
        "CS_ID" : CS_Number,
        "METHOD" : "REQUEST_START_TRANSACTION",
        "PAYLOAD" : payload
    }

    response = await broker.send_request(message)
    return response  

@app.get("/GetTransactionStatus/{CS_Number}")
async def GetTransactionStatus(CS_Number: int, transactionId: str = None ):
    message = {
        "CS_ID" : CS_Number,
        "METHOD" : "GET_TRANSACTION_STATUS",
        "PAYLOAD" : {"transaction_id" : transactionId}
    }
    response = await broker.send_request(message)
    return response


@app.on_event("startup")
async def main():

    global broker
    broker = await API_Rabbit_Handler().connect()

    
if __name__ == '__main__':
      uvicorn.run(app, host="0.0.0.0", port=8000,loop= 'asyncio')
