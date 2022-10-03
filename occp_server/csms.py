import asyncio
import logging
import websockets
import pika
import json
from chargePointRepr import ChargePoint

from aio_pika import Message, connect, ExchangeType
from aio_pika.message import IncomingMessage
from aio_pika.abc import AbstractIncomingMessage

from csms_Rabbit_Handler import CSMS_Rabbit_Handler
from ocpp_server import OCPP_Server

logging.basicConfig(level=logging.INFO)


class CSMS:

    def __init__(self):
        self.connected_cp = {}


    async def new_cp(self,websocket, charge_point_id):
        
        cp = ChargePoint(charge_point_id, websocket)

        self.connected_cp[charge_point_id] = cp

        await cp.start()


    
    async def on_api_request(self, message: AbstractIncomingMessage) -> None:
        """API sent a message"""

        #assert message.reply_to is not None
        content = json.loads(message.body.decode())

        logging.info("Received from API: %s", str(content))

        await message.ack()

        response = "RESPONSE".encode()

        await self.broker.channel.default_exchange.publish(
            Message(
                body=response,
                correlation_id=message.correlation_id,
            ),
            routing_key=message.reply_to,
        )


    async def run(self):

        self.ocpp_server = OCPP_Server()
        self.broker = CSMS_Rabbit_Handler()

        await self.broker.connect(self.new_cp)
        await self.ocpp_server.start_server(self.on_cp_connect)



if __name__ == '__main__':
    asyncio.run(CSMS().run())
