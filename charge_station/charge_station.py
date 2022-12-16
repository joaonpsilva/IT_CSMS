import logging
import asyncio
import websockets
from charge_station_Rabbit_Handler import Charge_Station_Rabbit_Handler, Fanout_Message
from ocpp.v201 import call
from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call, call_result, enums, datatypes
from ocpp.routing import after,on

import sys
logging.basicConfig(level=logging.INFO)


class ChargePoint(cp):

    def __init__(self, cp_id, ws):
        super().__init__(cp_id, ws)

        self.method_mapping = {
            "request_boot_notification" : call.BootNotificationPayload
        }

    async def run(self):
        #broker handles the rabbit mq queues and communication between services
        self.broker = Charge_Station_Rabbit_Handler(self.handle_request)
        await self.broker.connect()

        await self.start()

    
    async def handle_request(self, request):
        if request.intent in self.method_mapping:
            return await self.call(self.method_mapping[request.intent](**request.content))

    
    @on('TriggerMessage')
    async def on_TriggerMessage(self, **kwargs):

        message = Fanout_Message(intent="TriggerMessage", type="REQUEST", content=kwargs)
        await self.broker.ocpp_log(message)

        return call_result.TriggerMessagePayload(
            status=enums.TriggerMessageStatusType.accepted
        )

    



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