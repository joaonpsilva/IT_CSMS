import logging
import asyncio
import websockets

from os import path
import sys

sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
from fanout_Rabbit_Handler import Fanout_Rabbit_Handler, Fanout_Message

from ocpp.v201 import call
from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call, call_result, enums, datatypes
from ocpp.routing import after,on

logging.basicConfig(level=logging.INFO)


class ChargePoint(cp):

    def __init__(self, cp_id, ws):
        super().__init__(cp_id, ws)

        self.method_mapping = {
            "request_boot_notification" : self.bootNotification,
            "request_authorize" : self.authorize
        }

        self.accepted = False
        

    async def run(self):
        #broker handles the rabbit mq queues and communication between services
        self.broker = Fanout_Rabbit_Handler(self.handle_request, "OCPPclient")
        await self.broker.connect()

        await self.start()

    
    async def handle_request(self, request):
        if request.intent in self.method_mapping:
            return await self.method_mapping[request.intent](**request.content)
    
    
    async def bootNotification(self, **kwargs):
        #TODO B01.FR.06

        request = call.BootNotificationPayload(**kwargs)
        response = await self.call(request)

        loop = asyncio.get_event_loop()

        if response.status == enums.RegistrationStatusType.accepted:
            self.accepted = True
            #TODO status notification
            #initiate heart beat
            loop.create_task(self.heartBeat(response.interval))

        else:
            #Retry boot after x senconds
            loop.call_later(response.interval, loop.create_task, self.bootNotification(**kwargs))
        

    
    async def heartBeat(self, interval):
        while True:
            request = call.HeartbeatPayload()
            response = await self.call(request)
            await asyncio.sleep(interval)
        
    
    async def authorize(self, **kwargs):

        message = Fanout_Message(intent="get_IdToken_Info", content={"id_token": kwargs["id_token"]})
        response = await self.broker.send_request_wait_response(message)

        if response["status"] == "OK":
            if response["content"]["id_token"]["id_token"] == kwargs["id_token"]["id_token"]:
                print(response)
        
        return
        #local
        request = call.AuthorizePayload(**kwargs)
        response = await self.call(request)



    #---------------------------------------------------------------------------------
    
    @on('TriggerMessage')
    async def on_TriggerMessage(self, **kwargs):

        #message = Fanout_Message(intent="TriggerMessage", content=kwargs)
        #wait self.broker.ocpp_log(message)

        return call_result.TriggerMessagePayload(
            status=enums.TriggerMessageStatusType.accepted
        )    

    @on('RequestStartTransaction')
    async def on_RequestStartTransaction(self, **kwargs):

        message = Fanout_Message(intent="remote_start_transaction", content=kwargs)
        response = await self.broker.send_request_wait_response(message)
        
        return call_result.RequestStartTransactionPayload(**response)
    

    @on('RequestStopTransaction')
    async def on_RequestStopTransaction(self, **kwargs):

        message = Fanout_Message(intent="remote_stop_transaction", content=kwargs)
        response = await self.broker.send_request_wait_response(message)

        return call_result.RequestStopTransactionPayload(**response)

    
    async def getLocalListVersionFromDb(self):
    
        message = Fanout_Message(intent="SELECT", content={"table":"LocalList"})
        response = await self.broker.send_request_wait_response(message)

        return response["content"][-1]["version_number"]
    

    @on("GetLocalListVersion")
    async def on_GetLocalListVersion(self):
        return call_result.GetLocalListVersionPayload(version_number= await self.getLocalListVersionFromDb())
    
    @on("SendLocalList")
    async def on_SendLocalList(self, **kwargs):

        current_version = await self.getLocalListVersionFromDb()
        if 0 >= kwargs["version_number"] <= current_version:
            status = enums.SendLocalListStatusType.version_mismatch
        else:
            message = Fanout_Message(intent="SendLocalList", content=kwargs)
            response = await self.broker.send_request_wait_response(message)

            if response["status"] == "OK":
                status = enums.SendLocalListStatusType.accepted
            else:
                status = enums.SendLocalListStatusType.failed

        return call_result.SendLocalListPayload(status=status)

    
    @on('GetVariables')
    def on_get_variables(self,get_variable_data,**kwargs):
        
        get_variable_result = [
            datatypes.GetVariableResultType(
                attribute_status= enums.GetVariableStatusType.rejected, 
                component=var["component"],
                variable= var["variable"],
            )   
            for var in get_variable_data]

        return call_result.GetVariablesPayload(get_variable_result=get_variable_result)


    

async def main(cp_id):

    logging.info("Trying to connect to csms with id %s", cp_id)

    async with websockets.connect(
        'ws://{cp_id}:{password}@localhost:9000/{cp_id}'.format(cp_id = cp_id, password='passcp1'),
        
            subprotocols=['ocpp2.0.1']
    ) as ws:

        cp = ChargePoint(cp_id, ws)
        await cp.run()


if __name__ == '__main__':
   asyncio.run(main(sys.argv[1]))