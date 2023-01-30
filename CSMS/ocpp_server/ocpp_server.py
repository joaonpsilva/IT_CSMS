import websockets
import logging
from chargePointRepr import ChargePoint
from csms_Rabbit_Handler import CSMS_Rabbit_Handler, Rabbit_Message
import asyncio
import argparse
import signal
import sys

logging.basicConfig(level=logging.INFO)

def Basic_auth_with_broker(broker):
    class BasicAuth(websockets.BasicAuthWebSocketServerProtocol):
        def __init__(self, *args, **kwargs):
            super(BasicAuth, self).__init__(*args, **kwargs)
            self.broker = broker
        
        async def check_credentials(self, username, password):
            self.user = username
            self.password = password

            try:
                content = {"CP_ID" : username,"password": password}
                message = Rabbit_Message(origin = "ocppserver", destination="db1", method = "verify_password", cp_id=username, content=content)
                response =  await self.broker.send_request_wait_response(message)
                return response["content"]['approved']
            except:
                return False

    return BasicAuth


class OCPP_Server:

    def __init__(self):
        self.broker = None
        self.connected_CPs = {}
    
    def shut_down(self, sig, frame):
        logging.info("OCPP Server Shuting down")
        sys.exit(0)
    

    async def run(self, port, rb):
        #broker handles the rabbit mq queues and communication between services
        self.broker = CSMS_Rabbit_Handler("Ocpp_server", self.handle_api_request)
        await self.broker.connect(rb)

        #set same broker for all charge point connections
        ChargePoint.broker = self.broker
        
        #start server
        await self.start_server(port)
    

    async def start_server(self, port):

        BasicAuth_Custom_Handler = Basic_auth_with_broker(self.broker)
        server = await websockets.serve(
            self.on_cp_connect,
            '0.0.0.0',
            port,
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
    

    async def handle_api_request(self, request):
        """Function that handles requests from the api to comunicate with CPs"""

        #wich CP send the message to
        cp_id = request.cp_id

        if cp_id is None:
            #api wants to know current connected cps
            if request.method == "get_connected_cps":
                return {"status" : "OK", "content": list(self.connected_CPs.keys())}
            
            if request.method == "getTransactionStatus":
                try:
                    cp_id = await self.get_cpID_by_TransactionId(request.content["transaction_id"])
                except:
                    return {"status":"VAL_ERROR", "content": "Unknown Transaction"}


        if cp_id in self.connected_CPs:
            #if is connected
            status, content = await self.connected_CPs[str(cp_id)].send_CP_Message(**request.__dict__)
            return {"status" : status, "content": content}
        else:
            return {"status":"VAL_ERROR", "content": "This CP is not connected"}
    

    async def get_cpID_by_TransactionId(self, transaction_id):
        message = Rabbit_Message(method="select", content={"table":"Transaction_Event", "filters": {"transaction_id" : transaction_id}})
        response = await ChargePoint.broker.send_request_wait_response(message)

        if len(response["content"]) > 0:
            return response["content"][0]["cp_id"]


if __name__ == '__main__':
    #READ ARGUMENTS
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", type=int, default = 9000, help="OCPP server port")
    parser.add_argument("-rb", type=str, default = "amqp://guest:guest@localhost/", help="RabbitMq")
    args = parser.parse_args()

    #init server
    ocpp_server = OCPP_Server()
    
    #shut down handler
    signal.signal(signal.SIGINT, ocpp_server.shut_down)

    asyncio.run(ocpp_server.run(args.p, args.rb))