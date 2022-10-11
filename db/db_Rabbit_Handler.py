from aio_pika import ExchangeType, Message, connect
import uuid
import json
import asyncio
from typing import MutableMapping

from aio_pika.abc import (
    AbstractChannel, AbstractConnection, AbstractIncomingMessage, AbstractQueue,
)
import logging

logging.basicConfig(level=logging.INFO)

import dataclasses

class EnhancedJSONEncoder(json.JSONEncoder):
    """Extend json encoder to be able to json encode @dataclasses used by the ocpp library"""
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)

class DB_Rabbit_Handler:

    def __init__(self, request_queue_callback_function, store_queue_callback_function):

        self.loop = asyncio.get_running_loop()
        self.request_queue_callback_function = request_queue_callback_function
        self.store_queue_callback_function = store_queue_callback_function

    
    async def connect(self):
        """
        connect to the rabbitmq server and setup connection
        """

        #Declare connection
        self.connection = await connect("amqp://guest:guest@localhost/")

        #declare channel
        self.channel = await self.connection.channel()

        #Declare exchange where requests will be received
        self.request_Exchange = await self.channel.declare_exchange(name="requests", type=ExchangeType.TOPIC)
        #Declare exchange where logs are retrived
        self.db_store_Exchange = await self.channel.declare_exchange("db_store", type=ExchangeType.FANOUT)


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
    

    async def unpack(self, message: AbstractIncomingMessage):
        #manually acknowledge
        await message.ack()

        #load json content
        return json.loads(message.body.decode())

    
    async def on_store(self, message: AbstractIncomingMessage) -> None:
        """Received message to store"""

        content = await self.unpack(message)
        await self.store_queue_callback_function(content)


    async def on_request(self, message: AbstractIncomingMessage) -> None:
        """Received message from with a request"""

        content = await self.unpack(message)
        response = await self.request_queue_callback_function(content)
        
        #send response to the api if requested
        if message.reply_to is not None:
            await self.channel.default_exchange.publish(
                Message(
                    body=json.dumps(response, cls=EnhancedJSONEncoder).encode(),
                    correlation_id=message.correlation_id,
                ),
                routing_key=message.reply_to,
            )
