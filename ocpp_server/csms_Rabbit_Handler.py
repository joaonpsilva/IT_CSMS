from aio_pika import ExchangeType, Message, connect
import uuid
import json
import asyncio
from typing import MutableMapping

from aio_pika.abc import (
    AbstractChannel, AbstractConnection, AbstractIncomingMessage, AbstractQueue,
)

class CSMS_Rabbit_Handler:

    def __init__(self):

        self.loop = asyncio.get_running_loop()

    
    async def connect(self, callback_function):
        """
        connect to the rabbitmq server and setup connection
        """

        #Declare connection
        self.connection = await connect("amqp://guest:guest@localhost/")

        #declare channel
        self.channel = await self.connection.channel()

        #Declare exchange to where API will send requests
        self.request_Exchange = await self.channel.declare_exchange(name="requests", type=ExchangeType.TOPIC)

        #Declare queue that will receive the requests to be handled by the occp_server
        self.request_queue = await self.channel.declare_queue("occpServer_Requests_Queue")

        #Bind queue to exchange so that the queue is eligible to receive requests
        await self.request_queue.bind(self.request_Exchange, routing_key='request.ocppserver')

        await self.request_queue.consume(callback_function, no_ack=False)

        return self
