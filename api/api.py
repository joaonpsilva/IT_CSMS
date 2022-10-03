import uvicorn
from fastapi import FastAPI, Depends
from api_Rabbit_Handler import API_Rabbit_Handler

import asyncio

app = FastAPI()
broker = None


@app.get("/{CS_Number}/GetVariablesRequest")
async def GetVariablesRequest(CS_Number: int):
    message = {
        "content" : "Hello"
    }

    print(message)

    reponse = await broker.send_get_request(message)

    print(str(reponse))

    return str(reponse)



@app.on_event("startup")
async def main():

    global broker
    broker = await API_Rabbit_Handler().connect()

    
if __name__ == '__main__':
      uvicorn.run(app, host="0.0.0.0", port=8000,loop= 'asyncio')
