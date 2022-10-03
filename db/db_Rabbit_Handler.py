from aio_pika import ExchangeType, Message, connect
import uuid
import json
import asyncio
from typing import MutableMapping

from aio_pika.abc import (
    AbstractChannel, AbstractConnection, AbstractIncomingMessage, AbstractQueue,
)

class DB_Rabbit_Handler:

    def __init__(self):

        self.loop = asyncio.get_running_loop()

    
    async def connect(self, request_queue_callback_function, log_queue_callback_function):
        """
        connect to the rabbitmq server and setup connection
        """

        #Declare connection
        self.connection = await connect("amqp://guest:guest@localhost/")

        #declare channel
        self.channel = await self.connection.channel()

        #Declare exchange to where API will send requests
        self.request_Exchange = await self.channel.declare_exchange(name="requests", type=ExchangeType.TOPIC)

        #Declare queue that will receive the requests to be handled by the db
        self.request_queue = await self.channel.declare_queue("DB_Requests_Queue")

        #Declare queue that will receive stuff to save in the db
        self.log_queue = await self.channel.declare_queue("DB_Log_Queue")

        #Bind queue to exchange so that the queue is eligible to receive requests
        await self.request_queue.bind(self.request_Exchange, routing_key='request.db')

        await self.request_queue.consume(request_queue_callback_function, no_ack=False)
        await self.log_queue.consume(log_queue_callback_function, no_ack=False)

        return self
