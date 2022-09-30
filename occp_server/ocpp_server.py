import websockets
import logging

logging.basicConfig(level=logging.INFO)


class OCPP_Server:

    async def start_server(self, callback_function):
        server = await websockets.serve(
            callback_function,
            '0.0.0.0',
            9000,
            subprotocols=['ocpp2.0.1']
        )
        logging.info("WebSocket Server Started")

        

        await server.wait_closed()