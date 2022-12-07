import logging
logging.basicConfig(level=logging.INFO)


import sys
from os import path
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
from rabbit_handler import Rabbit_Handler

class DB_Rabbit_Handler(Rabbit_Handler):


    async def connect(self, create_response_queue=False):
        """
        connect to the rabbitmq server and setup connection
        """

        await super().connect(create_response_queue)
        

        #Declare queue that will receive the requests to be handled by the db
        self.request_queue = await self.channel.declare_queue("DB_Requests_Queue")

        #Bind queue to exchange so that the queue is eligible to receive requests
        await self.request_queue.bind(self.request_Exchange, routing_key='request.db.db1')
        await self.request_queue.bind(self.request_Exchange, routing_key='store.#')

        await self.request_queue.consume(self.on_request, no_ack=False)
    
