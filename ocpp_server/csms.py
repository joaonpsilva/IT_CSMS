import asyncio
import logging
from chargePointRepr import ChargePoint

from csms_Rabbit_Handler import CSMS_Rabbit_Handler
from ocpp_server import OCPP_Server

logging.basicConfig(level=logging.INFO)


class CSMS:

    def __init__(self):
        self.connected_CPs = {}
        

    async def new_cp(self,websocket, charge_point_id):
        """Call back funtion called by ocpp server when new CP connects"""
        
        #create new charge point object that will handle the comunication
        cp = ChargePoint(charge_point_id, websocket)

        #add to known connections
        self.connected_CPs[charge_point_id] = cp

        #start comunication
        await cp.start()


    
    async def handle_api_request(self, request) -> None:
        """Funtions that handles requests from the api to comunicate with CPs"""

        cp_id = request['CS_ID']

        response = await self.connected_CPs[str(cp_id)].send_CP_Message(
                request["METHOD"], request["PAYLOAD"])

        return response



    async def run(self):

        #broker handles the rabbit mq queues and communication between services
        self.broker = CSMS_Rabbit_Handler(self.handle_api_request)
        ChargePoint.broker = self.broker

        #OCPP server listens to CP connections
        self.ocpp_server = OCPP_Server(self.new_cp, self.broker)

        #start broker and server
        await self.broker.connect()
        await self.ocpp_server.start_server()



if __name__ == '__main__':
    asyncio.run(CSMS().run())
