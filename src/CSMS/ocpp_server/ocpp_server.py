import websockets
import logging
from CSMS.ocpp_server.chargePointRepr import ChargePoint

from rabbit_mq.rabbit_handler import Rabbit_Handler
from rabbit_mq.Rabbit_Message import Topic_Message

from rabbit_mq.exceptions import ValidationError
import asyncio
import argparse
import signal
import sys
import json

import ssl

logging.basicConfig(level=logging.INFO)

LOGGER = logging.getLogger("Ocpp_Server")

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
                message = Topic_Message(destination="SQL_DB", method = "verify_password", cp_id=username, content=content)
                response =  await self.broker.send_request_wait_response(message)
                return response['approved']
            except:
                return False

    return BasicAuth


class OCPP_Server:

    def __init__(self):
        self.broker = None
        self.connected_CPs = {}
    

    def shut_down(self, sig, frame):
        LOGGER.info("OCPP Server Shuting down")

        with open(self.variables_file, "w") as outfile:
            outfile.write(json.dumps(ChargePoint.server_variables))

        sys.exit(0)
    

    async def run(self, port, rb, variables_file, security_profile):
        #broker handles the rabbit mq queues and communication between services
        try:
            self.broker = Rabbit_Handler("Ocpp_Server", self.handle_api_request)
            await self.broker.connect(rb, receive_logs=False)
        except:
            LOGGER.error("Could not connect to RabbitMq")

        #set same broker for all charge point connections
        ChargePoint.broker = self.broker

        #read variables
        try:
            self.variables_file = variables_file
            with open(self.variables_file, 'r') as openfile:
                # Reading from json file
                json_object = json.load(openfile)
                ChargePoint.server_variables = json_object
        except:
            LOGGER.error("Could not read variables file")

        #start server
        await self.start_server(port, security_profile)
    

    async def start_server(self, port, security_profile):

        BasicAuth_Custom_Handler=None
        ssl_context=None

        #Security profile settings
        if security_profile in [1, 2]:
            BasicAuth_Custom_Handler = Basic_auth_with_broker(self.broker)

        if security_profile == 2:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            # Generate with Lets Encrypt, copied to this location, chown to current user and 400 permissions
            ssl_cert = "certs/ssl/localhost.crt"
            ssl_key = "certs/ssl/localhost.decrypted.key"
            ssl_context.load_cert_chain(ssl_cert, keyfile=ssl_key)

        server = await websockets.serve(
            self.on_cp_connect,
            '0.0.0.0',
            port,
            subprotocols=['ocpp2.0.1'],
            create_protocol=BasicAuth_Custom_Handler, 
            ssl=ssl_context
        )
        LOGGER.info("WebSocket Server Started")

        await server.wait_closed()

    
    async def verify_protocols(self, websocket):
        try:
            requested_protocols = websocket.request_headers[
                'Sec-WebSocket-Protocol']
        except KeyError:
            LOGGER.info("Client hasn't requested any Subprotocol. "
                    "Closing Connection")
            return await websocket.close()
        
        if websocket.subprotocol:
            LOGGER.info("Protocols Matched: %s", websocket.subprotocol)
        else:
            # In the websockets lib if no subprotocols are supported by the
            # client and the server, it proceeds without a subprotocol,
            # so we have to manually close the connection.
            LOGGER.warning('Protocols Mismatched | Expected Subprotocols: %s,'
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
            LOGGER.warning("Id already taken | Closing connection")
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
            LOGGER.warning("CP closed the connection")

        #when cp ends remove from connections
        await cp.set_on_off(False)
        self.connected_CPs.pop(charge_point_id)
    

    async def handle_api_request(self, request):
        """Function that handles requests from the api to comunicate with CPs"""

        #wich CP send the message to
        cp_id = request.cp_id

        if cp_id is None:
            #api wants to know current connected cps
            if request.method == "get_connected_cps":
                return list(self.connected_CPs.keys())
            
        if cp_id in self.connected_CPs:
            #if is connected
            content = await self.connected_CPs[str(cp_id)].send_CP_Message(**request.__dict__)
            return content
        else:
            raise ValidationError("This CP is not connected")


if __name__ == '__main__':
    #READ ARGUMENTS
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", type=int, default = 9000, help="OCPP server port")
    parser.add_argument("-rb", type=str, default = "amqp://guest:guest@localhost/", help="RabbitMq")
    parser.add_argument("-vf", type=str, default = "CSMS/ocpp_server/ocpp_server_variables.json", help="variables_file")
    parser.add_argument("-s", type=int, default = 2, help="Security Profile")

    args = parser.parse_args()

    #init server
    ocpp_server = OCPP_Server()
    
    #shut down handler
    signal.signal(signal.SIGINT, ocpp_server.shut_down)
    signal.signal(signal.SIGTERM, ocpp_server.shut_down)

    asyncio.run(ocpp_server.run(args.p, args.rb, args.vf, args.s))