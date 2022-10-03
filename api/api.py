import uvicorn
from fastapi import FastAPI, Depends
from api_Rabbit_Handler import API_Rabbit_Handler
from pydantic import BaseModel
from typing import Dict, List, Optional
from ocpp.v201 import call, call_result, enums, datatypes


import asyncio

app = FastAPI()
broker = None


#class GetVariablesRequestBody(BaseModel):
#    getVariableData: List[datatypes.GetVariableDataType]


@app.post("/GetVariablesRequest/{CS_Number}")
async def GetVariablesRequest(CS_Number: int, payload: List[datatypes.GetVariableDataType]):
    
    message = {
        "CS_ID" : CS_Number,
        "Message" : payload
    }

    response = await broker.send_get_request(message)

    return response



@app.on_event("startup")
async def main():

    global broker
    broker = await API_Rabbit_Handler().connect()

    
if __name__ == '__main__':
      uvicorn.run(app, host="0.0.0.0", port=8000,loop= 'asyncio')
