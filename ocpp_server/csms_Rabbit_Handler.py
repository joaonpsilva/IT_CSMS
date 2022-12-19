import sys
from os import path
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
from rabbit_handler import Rabbit_Handler, Rabbit_Message

import logging
logging.basicConfig(level=logging.INFO)


class CSMS_Rabbit_Handler(Rabbit_Handler):
    """class that will handle communication inter services"""

    
    async def connect(self):
        """
        connect to the rabbitmq server and setup connection
        """

        await super().connect()

        #Declare queue that will receive the requests to be handled by the occp_server
        self.request_queue = await self.channel.declare_queue("OCCPserver_Request_Queue")
        #Bind queue to exchange so that the queue is eligible to receive requests
        await self.request_queue.bind(self.exchange, routing_key='request.ocppserver.#')
        #Start consuming requests from the queue
        await self.request_queue.consume(self.on_request, no_ack=False)


        #declare a callback queue to where the reponses will be consumed
        self.response_queue = await self.channel.declare_queue("OCCPserver_Response_Queue", exclusive=True)
        await self.response_queue.bind(self.exchange, routing_key='response.ocppserver.#')
        #consume messages from the queue
        await self.response_queue.consume(self.on_response)
    
    async def ocpp_log(self, message):
        message.type = "ocpp_log"
        message.origin = "ocppserver"
        return await super().ocpp_log(message)
    
    async def send_request_wait_response(self, message):
        message.destination = "db1"
        message.origin = "ocppserver"
        return await super().send_request_wait_response(message)
    


