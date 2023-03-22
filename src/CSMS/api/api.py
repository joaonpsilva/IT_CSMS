import uvicorn
from fastapi import FastAPI, Depends, Query, Response, status, Request, HTTPException
from enum import Enum

from typing import List, Optional
from ocpp.v201 import call, call_result, enums
from CSMS.api.schemas import datatypes
from CSMS.api.schemas import payloads
from CSMS.api.schemas import schemas
from CSMS.api.auth import AuthHandler
from CSMS.api.service import API_Service
from rabbit_mq.exceptions import OtherError
import asyncio
import logging
from sse_starlette.sse import EventSourceResponse

import argparse
import datetime
import sys

parser = argparse.ArgumentParser()
parser.add_argument("-p", type=int, default = 8000, help="OCPP server port")
parser.add_argument("-rb", type=str, default = "amqp://guest:guest@localhost/", help="RabbitMq")
args = parser.parse_args()

LOGGER = logging.getLogger("API")
LOGGER.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
LOGGER.addHandler(ch)


app = FastAPI()
auth_handler = AuthHandler()
service = API_Service()

##################################################################

@app.post("/register", status_code=201)
async def register(email: str, password:str, full_name:str, status:str, cust_id:int, id_token:str=None):
    values = {"email": email, "password":password, "full_name":full_name, "status":status, "cust_id":cust_id, "_id_token":id_token}
    return await service.send_request("register", payload=values, destination="SQL_DB")


@app.get("/login", status_code=200)
async def login(email: str, password:str):
    try:
        response = await service.send_request("login", payload={"email": email, "password":password}, destination="SQL_DB")
        token = auth_handler.encode_token(response)
        return {"token" : token}
    except OtherError as e:
        raise HTTPException(401, detail=e.args[0])
        

@app.get("/users", status_code=200)
async def getUsers():
    return await service.send_request("select", payload={"table": "User"}, destination="SQL_DB")

@app.get("/users/{email}", status_code=200)
async def get_user_byEmail(email:str):
    return await service.send_request("select", payload={"table": "User", "filters":{"email":email}}, destination="SQL_DB")


@app.post("/create_GroupidToken/", status_code=201)
async def create_GroupidToken(type:enums.IdTokenType = enums.IdTokenType.local, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("create_new_Group_IdToken", payload={"type": type}, destination="SQL_DB")

@app.post("/create_idToken/", status_code=201)
async def create_idToken(id_token_info:schemas.new_IdToken, user=Depends(auth_handler.check_permission_level_2)):
    return await service.create_new_IdToken(id_token_info)

@app.post("/give_group_to_idToken/", status_code=201)
async def give_group_to_idToken(id_token:str, group_id_token:str, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("update", payload={"table": "IdTokenInfo", "filters":{"_id_token":id_token}, "values":{"_group_id_token" : group_id_token}}, destination="SQL_DB")


@app.get("/group_idTokens/", status_code=200)
async def group_idTokens(user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("select", payload={"table": "GroupIdToken"}, destination="SQL_DB")


@app.get("/transactions", status_code=200)
async def getTransactions(transaction_id:str, user=Depends(auth_handler.check_permission_level_1)):
    return await service.send_request("select", payload={"table": "Transaction", "filters":{"transaction_id":transaction_id}}, destination="SQL_DB")

@app.get("/transactions/open/by_IdToken", status_code=200)
async def getOpenTransactionsByIdToken(user=Depends(auth_handler.check_permission_level_1)):
    if user["id_token"] is None:
        raise HTTPException(400, detail="User doesn't have an Id Token")
    return await service.send_request("get_Open_Transactions_byIdToken", payload={"id_token": user["id_token"]["id_token"]}, destination="SQL_DB")


@app.get("/transactions/open", status_code=200)
async def getOpenTransactions(user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("select", payload={"table":"Transaction", "filters":{"active":True}}, destination="SQL_DB")


@app.get("/transactions/{date}", status_code=200)
async def getOpenTransactionsByIdToken(date: datetime.datetime, user=Depends(auth_handler.check_permission_level_1)):
    if user["id_token"] is None:
        raise HTTPException(400, detail="User doesn't have an Id Token")
    return await service.send_request("get_Transactions_byDate", payload={"id_token": user["id_token"]["id_token"], "date":date}, destination="SQL_DB")


@app.post("/charge/start", status_code=200)
async def charge_start(evse_id: int, cp_id:str, user=Depends(auth_handler.check_permission_level_1)):

    if user["id_token"] is None:
        raise HTTPException(400, detail="User doesn't have an Id Token")

    id_token=datatypes.IdTokenType(id_token=user["id_token"]["id_token"], type=user["id_token"]["type"])

    payload = payloads.RequestStartTransactionPayload(
        id_token=id_token,
        evse_id=evse_id
    )
    return await service.send_request("requestStartTransaction", cp_id=cp_id, payload=payload)


@app.post("/charge/stop", status_code=200)
async def charge_stop(transaction_id: str, user=Depends(auth_handler.check_permission_level_1)):
    return await service.send_request("requestStopTransaction", payload={"transaction_id" : transaction_id})


@app.post("/setmaxpower", status_code=200)
async def setmaxpower(transaction_id: str, max_power: int, user=Depends(auth_handler.check_permission_level_1)):
    return await service.setmaxpower(transaction_id, max_power)



@app.post("/set_charging_limits", status_code=200)
async def set_charging_power(transaction_id: str, action:schemas.Charger_Action=None, power: int=None, max_soc:int=None, min_soc:int=None,user=Depends(auth_handler.check_permission_level_2)):
    return await service.set_transaction_limits(transaction_id, action, power, max_soc, min_soc)


@app.get("/getTransactions")
async def getTransactions(user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("select", payload={"table" : schemas.DB_Tables.Transaction}, destination="SQL_DB")


@app.get("/getConnected_ChargePoints/")
async def getConnected_ChargePoints():
    return await service.send_request("get_connected_cps")


@app.get("/stations", status_code=200)
async def stations():
    return await service.send_request("select", payload={"table": "Charge_Point"}, destination="SQL_DB")


@app.get("/stations/{cp_id}", status_code=200)
async def getStationById(cp_id : str):
    mode = {"evse":{"describe":False, "connector":{}, "reservation":{}}}
    return await service.send_request("select", payload={"table": "Charge_Point", "filters":{"cp_id":cp_id}, "mode":mode}, destination="SQL_DB")


@app.post("/update_auth_list/{cp_id}", status_code=200)
async def update_auth_list(cp_id: str, update_type:schemas.Update_type,id_tokens:List[str]=None,user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_authList(cp_id, update_type, id_tokens)


@app.post("/ReserveNow", status_code=200)
async def reserve_now(cp_id: str, evse_id: int, user=Depends(auth_handler.check_permission_level_1)):
    if user["id_token"] is None:
        raise HTTPException(400, detail="User doesn't have an Id Token")
    return await service.reserve(cp_id, evse_id, user["id_token"]["id_token"])

@app.post("/cancel_Reservation", status_code=200)
async def cancel_Reservation(reservation_id : int, user=Depends(auth_handler.check_permission_level_1)):
    return await service.cancel_reservation(reservation_id)


@app.post("/ChangeAvailability/{cp_id}", status_code=200)
async def ChangeAvailability(cp_id: str, payload: payloads.ChangeAvailabilityPayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("changeAvailability", cp_id, payload)

@app.post("/UnlockConnector/{cp_id}", status_code=200)
async def UnlockConnector(cp_id: str, payload: payloads.UnlockConnectorPayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("unlockConnector", cp_id, payload)


@app.post("/GetVariables/{cp_id}", status_code=200)
async def GetVariables(cp_id: str, payload: payloads.GetVariablesPayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("getVariables", cp_id, payload)


@app.post("/SetVariables/{cp_id}", status_code=200)
async def SetVariables(cp_id: str, payload: payloads.SetVariablesPayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("setVariables", cp_id, payload)


@app.post("/RequestStartTransaction/{cp_id}", status_code=200)
async def RequestStartTransaction(cp_id: str, payload: payloads.RequestStartTransactionPayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("requestStartTransaction", cp_id, payload)


@app.post("/RequestStopTransaction/{cp_id}", status_code=200)
async def RequestStopTransaction(cp_id: str, payload: call.RequestStopTransactionPayload, user=Depends(auth_handler.check_permission_level_2)):
    #TODO request stop transaction without cp id input?
    # request stop transaction with remote start id
    return await service.send_request("requestStopTransaction", cp_id, payload)


@app.post("/TriggerMessage/{cp_id}", status_code=200)
async def TriggerMessage(cp_id: str, payload: payloads.TriggerMessagePayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("triggerMessage", cp_id, payload)


@app.post("/GetCompositeSchedule/{cp_id}", status_code=200)
async def GetCompositeSchedule(cp_id: str, payload: payloads.GetCompositeSchedulePayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("getCompositeSchedule", cp_id, payload)
    #TODO make a get 

@app.post("/SetChargingProfile/{cp_id}", status_code=200)
async def SetChargingProfile(cp_id: str, payload: payloads.SetChargingProfilePayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("setChargingProfile", cp_id, payload)


@app.post("/GetChargingProfiles/{cp_id}", status_code=200)
async def GetChargingProfiles(cp_id: str, payload: payloads.GetChargingProfilesPayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("getChargingProfiles", cp_id, payload)
    #TODO make a get 


@app.post("/ClearChargingProfile/{cp_id}", status_code=200)
async def ClearChargingProfile(cp_id: str, payload: payloads.ClearChargingProfilePayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("clearChargingProfile", cp_id, payload)


@app.post("/GetBaseReport/{cp_id}", status_code=200)
async def GetBaseReport(cp_id: str, payload: payloads.GetBaseReportPayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("getBaseReport", cp_id, payload)
    #TODO make a get


@app.post("/ClearVariableMonitoring/{cp_id}", status_code=200)
async def ClearVariableMonitoring(cp_id: str, payload: payloads.ClearVariableMonitoringPayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("clearVariableMonitoring", cp_id, payload)


@app.post("/SetVariableMonitoring/{cp_id}", status_code=200)
async def SetVariableMonitoring(cp_id: str, payload: payloads.SetVariableMonitoringPayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("setVariableMonitoring", cp_id, payload)


@app.post("/GetMonitoringReport/{cp_id}", status_code=200)
async def getMonitoringReport(cp_id: str, payload: payloads.GetMonitoringReportPayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("getMonitoringReport", cp_id, payload)


@app.post("/Reset/{cp_id}", status_code=200)
async def Reset(cp_id: str, payload: payloads.ResetPayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("reset", cp_id, payload)


@app.post("/GetTransactionStatus/{cp_id}", status_code=200)
async def GetTransactionStatus(cp_id: str, payload: payloads.GetTransactionStatusPayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("getTransactionStatus", cp_id, payload)

@app.get("/GetTransactionStatus", status_code=200)
async def GetTransactionStatus(transaction_id: str, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("getTransactionStatus", payload={"transaction_id":transaction_id})


@app.post("/SetDisplayMessage/{cp_id}", status_code=200)
async def SetDisplayMessage(cp_id: str, payload: payloads.SetDisplayMessagePayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("setDisplayMessage", cp_id, payload)

@app.post("/GetDisplayMessages/{cp_id}", status_code=200)
async def GetDisplayMessages(cp_id: str, payload: payloads.GetDisplayMessagesPayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("getDisplayMessages", cp_id, payload)

@app.post("/ClearDisplayMessage/{cp_id}", status_code=200)
async def ClearDisplayMessage(cp_id: str, payload: payloads.ClearDisplayMessagePayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("clearDisplayMessage", cp_id, payload)


@app.post("/getInstalledCertificateIds/{cp_id}", status_code=200)
async def getInstalledCertificateIds(cp_id: str, payload: payloads.GetInstalledCertificateIdsPayload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request("getInstalledCertificateIds", cp_id, payload)


@app.post("/CRUD/", status_code=200)
async def CRUD(payload: schemas.CRUD_Payload, user=Depends(auth_handler.check_permission_level_2)):
    return await service.send_request(payload.operation, payload=payload, destination="SQL_DB")


@app.get('/stream')
async def message_stream(request: Request, events: List[enums.Action]= Query(
                    [],
                    title="Events"), user=Depends(auth_handler.check_permission_level_2)):

    if len(events) == 0:
        raise HTTPException(400, detail="specify at least 1 event")

    event_queue = asyncio.Queue()

    #put queue to receive events 
    for event in events:
        if event not in service.event_listeners:
            service.event_listeners[event] = []
        service.event_listeners[event].append(event_queue)
    

    async def event_generator():
        while True:
            # If client closes connection, stop sending events
            if await request.is_disconnected():
                #remove queue from listener
                for event in events:
                    service.event_listeners[event].remove(event_queue)
                break
            
            try:
                #read and yield events as they arrive
                new_event = await event_queue.get()
                yield new_event
                event_queue.task_done()
            except:
                pass
        
    return EventSourceResponse(event_generator())


@app.on_event("startup")
async def main():
    global service
    await service.start(args.rb)

    
if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=args.p,loop= 'asyncio')
