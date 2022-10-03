import websockets
import logging

logging.basicConfig(level=logging.INFO)


class OCPP_Server:

    def __init__(self):
        self.callback_funtion = None

    async def start_server(self, callback_function):

        self.callback_funtion = callback_function

        server = await websockets.serve(
            self.on_cp_connect,
            '0.0.0.0',
            9000,
            subprotocols=['ocpp2.0.1']
        )
        logging.info("WebSocket Server Started")

        await server.wait_closed()


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

        self.callback_funtion(websocket, path.strip('/'))