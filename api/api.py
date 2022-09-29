import uvicorn
from fastapi import FastAPI, Depends
from Request_Handler import Request_Handler

import asyncio

app = FastAPI()
request_handler = None


@app.get("/{CS_Number}/GetVariablesRequest")
async def GetVariablesRequest(CS_Number: int):
    message = {
        'content' : "Hello"
    }

    print("---Sending")
    print(message)

    reponse = request_handler.call(message)

    print("----Receiving")
    print(str(reponse))

    return str(reponse)



@app.on_event("startup")
async def main():

    request_handler = Request_Handler()
    print("AAAAa")

    #consumer_task = asyncio.create_task(request_handler.init_Consumer())
    print("BBBBbb")
    
if __name__ == '__main__':
      uvicorn.run(app, host="0.0.0.0", port=8000,loop= 'asyncio')
