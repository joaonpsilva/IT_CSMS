
import logging
logging.basicConfig(level=logging.INFO)

import sys
from os import path
sys.path.append( path.dirname(path.dirname( path.dirname( path.abspath(__file__) ) ) ))
from rabbit_handler import Rabbit_Handler, Rabbit_Message
            

class API_Rabbit_Handler(Rabbit_Handler):
    

    async def connect(self):
        """
        connect to the rabbitmq server and setup connection
        """

        await super().connect()


        self.request_queue = await self.channel.declare_queue("API_Event_Queue")
        await self.request_queue.bind(self.exchange, routing_key='ocpp_log.#')
        await self.request_queue.consume(self.on_request, no_ack=False)

        #declare a callback queue to where the reponses will be consumed
        self.response_queue = await self.channel.declare_queue("API_Response_Queue", exclusive=True)
        await self.response_queue.bind(self.exchange, routing_key='response.api.#')
        #consume messages from the queue
        await self.response_queue.consume(self.on_response)

