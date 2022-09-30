import asyncio
import logging
import websockets
import pika
import json
from chargePointRepr import ChargePoint

from aio_pika import Message, connect, ExchangeType
from aio_pika.abc import AbstractIncomingMessage

from occp_server_Request_Handler import Request_Handler
from ocpp_server import OCPP_Server

class CSMS:

    def __init__(self):
        self.connected_cp = {}



    async def on_connect(self,websocket, path):
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

        await cp.start()



    async def run(self):

        self.ocpp_server = OCPP_Server()
        self.request_handler = Request_Handler()

        await self.request_handler.connect()
        await self.ocpp_server.start_server(self.on_connect)



if __name__ == '__main__':
    asyncio.run(CSMS().run())
