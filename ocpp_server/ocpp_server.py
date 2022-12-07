import websockets
import logging
from chargePointRepr import ChargePoint
from csms_Rabbit_Handler import CSMS_Rabbit_Handler
import asyncio

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
                "method" : "VERIFY_PASSWORD",
                "cp_id" : username,
                "content" : {
                    "CP_ID" : username,
                    "password": password
                }
            }

            response =  await self.broker.send_request_wait_response(message)
            return response["content"]['approved']

    return BasicAuth


class OCPP_Server:

    def __init__(self):
        self.broker = None
        self.connected_CPs = {}
    

    async def run(self):
        #broker handles the rabbit mq queues and communication between services
        self.broker = CSMS_Rabbit_Handler(self.handle_api_request)
        await self.broker.connect()

        #set same broker for all charge point connections
        ChargePoint.broker = self.broker
        
        #start server
        await self.start_server()
    

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

    
    async def verify_protocols(self, websocket):
        try:
            requested_protocols = websocket.request_headers[
                'Sec-WebSocket-Protocol']
        except KeyError:
            logging.info("Client hasn't requested any Subprotocol. "
                    "Closing Connection")
            return await websocket.close()

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


    async def on_cp_connect(self,websocket, path):
        """ For every new charge point that connects, create a ChargePoint
        instance and start listening for messages.
        """
        charge_point_id = path.strip('/')

        if charge_point_id in self.connected_CPs:
            logging.warning("Id already taken | Closing connection")
            return await websocket.close()
        
        await self.verify_protocols(websocket)

        #create new charge point object that will handle the comunication
        cp = ChargePoint(charge_point_id, websocket)
        #add to known connections
        self.connected_CPs[charge_point_id] = cp
        #start comunication

        try:
            await cp.start()
        except websockets.exceptions.WebSocketException:
            logging.warning("CP closed the connection")

        #when cp ends remove from connections
        self.connected_CPs.pop(charge_point_id)
    

    async def handle_api_request(self, request) -> None:
        """Function that handles requests from the api to comunicate with CPs"""

        #api wants to know current connected cps
        if request['method'] == "GET_CONNECTED_CPS":
            return {"status" : "OK", "content": list(self.connected_CPs.keys())}

        #wich CP send the message to
        cp_id = request.pop('cp_id')
        if cp_id in self.connected_CPs:
            #if is connected
            status, content = await self.connected_CPs[str(cp_id)].send_CP_Message(**request)
            return {"status" : status, "content": content}
        else:
            return {"status":"VAL_ERROR", "content": "This CP is not connected"}


if __name__ == '__main__':
    asyncio.run(OCPP_Server().run())