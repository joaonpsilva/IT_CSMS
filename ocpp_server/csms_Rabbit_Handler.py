import sys
from os import path
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
from rabbit_handler import Rabbit_Handler, Rabbit_Message

import logging
logging.basicConfig(level=logging.INFO)


class CSMS_Rabbit_Handler(Rabbit_Handler):
    """class that will handle communication inter services"""

    
    async def connect(self, create_response_queue = True):
        """
        connect to the rabbitmq server and setup connection
        """

        await super().connect(create_response_queue)

        #Declare queue that will receive the requests to be handled by the occp_server
        self.request_queue = await self.channel.declare_queue("occpServer_Requests_Queue")
        #Bind queue to exchange so that the queue is eligible to receive requests
        await self.request_queue.bind(self.private_Exchange, routing_key='REQUEST.ocppserver.#')
        #Start consuming requests from the queue
        await self.request_queue.consume(self.on_request, no_ack=False)
    
    async def ocpp_log(self, message):
        message.type = "OCPP_LOG"
        message.origin = "ocppserver"
        return await super().ocpp_log(message)
    
    async def send_request_wait_response(self, message):
        message.destination = "db1"
        message.origin = "ocppserver"
        return await super().send_request_wait_response(message)
    


