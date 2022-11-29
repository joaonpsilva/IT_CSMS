
import logging
logging.basicConfig(level=logging.INFO)

import sys
from os import path
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
from rabbit_handler import Rabbit_Handler
            

class API_Rabbit_Handler(Rabbit_Handler):
    

    async def connect(self, create_response_queue = True):
        """
        connect to the rabbitmq server and setup connection
        """

        await super().connect(create_response_queue)


        self.request_queue = await self.channel.declare_queue("API_Event_Queue")
        await self.request_queue.bind(self.request_Exchange, routing_key='store.#')
        await self.request_queue.consume(self.on_request, no_ack=False)

