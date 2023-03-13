import asyncio
import websockets
import argparse
import sys
import signal
import re
import traceback

from rabbit_mq.fanout_Rabbit_Handler import Fanout_Rabbit_Handler
from rabbit_mq.Rabbit_Message import Fanout_Message

from ocpp.v201 import call
from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call, call_result, enums, datatypes

import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("websockets").setLevel(logging.CRITICAL)


class ChargePoint(cp):

    def __init__(self, cp_id, ws=None):
        super().__init__(cp_id, ws)
        self.connection_active = False
        
        self.implemented_actions = dict(self.route_map)

    
    def shut_down(self, sig, frame):
        logging.info("Shuting down")
        sys.exit(0)
    

    async def run(self, rabbit, server_port, password):

        #broker handles the rabbit mq queues and communication between services
        self.broker = Fanout_Rabbit_Handler("OCPPclient", self.rabbit_to_ocpp)
        await self.broker.connect(rabbit)

        #Connect to server CSMS        
        async for websocket in websockets.connect(
        'ws://{cp_id}:{password}@localhost:{server_port}/{cp_id}'.format(cp_id = self.id, password=password, server_port=server_port),
            subprotocols=['ocpp2.0.1']
        ):
            try:
                logging.info("Connection established with CSMS")

                self._connection = websocket
                self.connection_active = True

                await self.start()

            except websockets.ConnectionClosed:
                self.connection_active = False
                logging.info("Connection Error. Trying to restore connection")
                continue
    

    async def rabbit_to_ocpp(self, request):
        """
        CallBack function that is called when a request is received on RabbitMq
        """
        try:
            #remove "request_"
            assert(request.intent[:8] == "request_")
            words = request.intent[8:].split("_")

            #transform snake to camel and add "Payload"
            intent = "".join(s.title() for s in words) + "Payload"

            #Get the correct call Object
            request = getattr(call, intent)(**request.content)
        except:
            #request was no for ocpp client
            return

        try:
            #send message
            return await self.call(request, False)
        except Exception as e:
            logging.error(traceback.format_exc())

            return str(e.__class__.__name__)
    


    #HANDLE OCPP MESSAGES-----

    class Ocpp_Message_Handler:
        def __init__(self, action, broker):
            self.action = action
            self.broker = broker
        
        async def handle_message(self, **kwargs):
                
            #action to rabbitmq format
            intent = re.sub(r'(?<!^)(?=[A-Z])', '_', self.action).lower()
            message = Fanout_Message(intent=intent, content=kwargs)

            #send message
            response = await self.broker.send_request_wait_response(message, timeout=30)

            #get correct payload
            response = getattr(call_result, self.action + "Payload")(**response)    

            return response


    async def _handle_call(self, msg):

        if msg.action not in self.implemented_actions:
            message_handler = self.Ocpp_Message_Handler(msg.action, self.broker)
            self.route_map[msg.action] = {'_skip_schema_validation': False, '_on_action': message_handler.handle_message}
        
        await super()._handle_call(msg)


async def main(args):
    cp = ChargePoint(args.cp)

    #shut down handler
    signal.signal(signal.SIGINT, cp.shut_down)

    await cp.run(args.rb, args.p, args.pw)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", type=int, default = 9000, help="OCPP server port")
    parser.add_argument("-rb", type=str, default = "amqp://guest:guest@localhost/", help="RabbitMq")
    parser.add_argument("-cp", type=str, default = "CP_1", help="Cp_id")
    parser.add_argument("-pw", type=str, default = "passcp1", help="Cp password")
    args = parser.parse_args()

    asyncio.run(main(args))