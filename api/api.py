import uvicorn
from fastapi import FastAPI, Depends
from Request_Handler import Request_Handler

import asyncio

app = FastAPI()
request_handler = None


@app.get("/{CS_Number}/GetVariablesRequest")
async def GetVariablesRequest(CS_Number: int):
    message = {
        "content" : "Hello"
    }

    print("---Sending")
    print(message)

    reponse = await request_handler.call(message)

    print("----Receiving")
    print(str(reponse))

    return str(reponse)



@app.on_event("startup")
async def main():

    global request_handler
    request_handler = await Request_Handler().connect()

    
if __name__ == '__main__':
      uvicorn.run(app, host="0.0.0.0", port=8000,loop= 'asyncio')
