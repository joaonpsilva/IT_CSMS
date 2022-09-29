from aio_pika import ExchangeType, Message, connect
import uuid
import json
import asyncio
from typing import MutableMapping

from aio_pika.abc import (
    AbstractChannel, AbstractConnection, AbstractIncomingMessage, AbstractQueue,
)

class Request_Handler:

    def __init__(self):

        self.loop = asyncio.get_running_loop()

    
    async def connect(self):
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

        await self.request_queue.consume(self.on_api_request)

        return self


    
    async def on_api_request(self, message: AbstractIncomingMessage) -> None:

        #assert message.reply_to is not None
        n = json.loads(message.body.decode())

        print(n)
        response = "RESPONSE".encode()

        await self.channel.default_exchange.publish(
            Message(
                body=response,
                correlation_id=message.correlation_id,
            ),
            routing_key=message.reply_to,
        )
        print("Request complete")