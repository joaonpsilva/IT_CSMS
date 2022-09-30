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


    async def on_cp_connect(self,websocket, path):
        """ For every new charge point that connects, create a ChargePoint
        instance and start listening for messages.
        """
        try:
            requested_protocols = websocket.request_headers[
                'Sec-WebSocket-Protocol']
        except KeyError:
            logging.info("Client hasn't requested any Subprotocol. "
                    "Closing Connection")
        if websocket.subprotocol:
            logging.info("Protocols Matched: %s", websocket.subprotocol)
        else:
            # In the websockets lib if no subprotocols are supported by the
            # client and the server, it proceeds without a subprotocol,
            # so we have to manually close the connection.
            logging.warning('Protocols Mismatched | Expected Subprotocols: %s,'
                            ' but client supports  %s | Closing connection',
                            websocket.available_subprotocols,
                            requested_protocols)
            return await websocket.close()

        charge_point_id = path.strip('/')
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

        await self.broker.connect(self.on_api_request)
        await self.ocpp_server.start_server(self.on_cp_connect)



if __name__ == '__main__':
    asyncio.run(CSMS().run())
