import asyncio
import logging
import websockets
import pika
import json
from chargePointRepr import ChargePoint

from aio_pika import Message, connect, ExchangeType
from aio_pika.abc import AbstractIncomingMessage

from occp_server_Request_Handler import Request_Handler

logging.basicConfig(level=logging.INFO)



async def on_connect(websocket, path):
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



async def main():
    server = await websockets.serve(
        on_connect,
        '0.0.0.0',
        9000,
        subprotocols=['ocpp2.0.1']
    )
    logging.info("WebSocket Server Started")

    request_handler = await Request_Handler().connect()

    await server.wait_closed()



if __name__ == '__main__':
    asyncio.run(main())
