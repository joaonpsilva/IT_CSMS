
from aio_pika.abc import AbstractIncomingMessage

import logging
logging.basicConfig(level=logging.INFO)


import sys
from os import path
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
from rabbit_handler import Rabbit_Handler

class DB_Rabbit_Handler(Rabbit_Handler):

    def __init__(self, handle_request, handle_store):

        super().__init__(handle_request)
        self.handle_store = handle_store

    
    async def connect(self, create_response_queue=False):
        """
        connect to the rabbitmq server and setup connection
        """

        await super().connect(create_response_queue)
        

        #Declare queue that will receive the requests to be handled by the db
        self.request_queue = await self.channel.declare_queue("DB_Requests_Queue")
        #Declare queue that will receive stuff to save in the db
        self.db_store_queue = await self.channel.declare_queue("DB_store_Queue")


        #Bind queue to exchange so that the queue is eligible to receive requests
        await self.request_queue.bind(self.request_Exchange, routing_key='request.db')
        #Bind queue to exchange so that the queue is eligible to log requests
        await self.db_store_queue.bind(self.db_store_Exchange, routing_key='thisisignored')


        await self.request_queue.consume(self.on_request, no_ack=False)
        await self.db_store_queue.consume(self.on_store, no_ack=False)
    

    async def on_store(self, message: AbstractIncomingMessage) -> None:
        """Received message to store"""

        content = await self.unpack(message)
        logging.info("RabbitMQ RECEIVED info to store: %s", str(content))

        await self.handle_store(content)

