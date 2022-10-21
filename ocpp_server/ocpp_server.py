import websockets
import logging

logging.basicConfig(level=logging.INFO)

def Basic_auth_with_broker(broker):

    class BasicAuth(websockets.BasicAuthWebSocketServerProtocol):
        def __init__(self, *args, **kwargs):
            super(BasicAuth, self).__init__(*args, **kwargs)
            self.broker = broker
        
        async def check_credentials(self, username, password):
            self.user = username
            self.password = password

            message = {
                "CS_ID" : CS_Number,
                "METHOD" : "GET_PASSWORD",
            }

            reponse =  await self.broker.send_request(message)

            return True
    
    return BasicAuth


class OCPP_Server:

    def __init__(self, callback_function, broker):
        self.callback_funtion = callback_function
        self.broker = broker
    
    async def start_server(self):

        BasicAuth_Custom_Handler = Basic_auth_with_broker(self.broker)
        
        server = await websockets.serve(
            self.on_cp_connect,
            '0.0.0.0',
            9000,
            subprotocols=['ocpp2.0.1'],
            create_protocol=BasicAuth_Custom_Handler
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

        await self.callback_funtion(websocket, path.strip('/'))