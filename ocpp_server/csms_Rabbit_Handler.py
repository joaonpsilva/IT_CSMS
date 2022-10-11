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


class CSMS_Rabbit_Handler:
    """class that will handle communication inter services"""


    def __init__(self, csms_handle_request):

        self.loop = asyncio.get_running_loop()

        #csms callback funtion that will handle api requests
        self.csms_handle_request = csms_handle_request

    
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
        #Declare exchange where logs are sent
        self.db_store_Exchange = await self.channel.declare_exchange("db_store", type=ExchangeType.FANOUT)

        #Declare queue that will receive the requests to be handled by the occp_server
        self.request_queue = await self.channel.declare_queue("occpServer_Requests_Queue")

        #Bind queue to exchange so that the queue is eligible to receive requests
        await self.request_queue.bind(self.request_Exchange, routing_key='request.ocppserver')

        #Start consuming requests from the queue
        await self.request_queue.consume(self.on_api_request, no_ack=False)
    

    async def on_api_request(self, message: AbstractIncomingMessage) -> None:
        """Received message from with a request"""

        #manually acknowledge
        await message.ack()

        #load json content
        content = json.loads(message.body.decode())
        logging.info("Received from API: %s", str(content))

        #pass content to csms
        response = await self.csms_handle_request(content)
        
        #send response to the api if requested
        if message.reply_to is not None:
            await self.channel.default_exchange.publish(
                Message(
                    body=json.dumps(response, cls=EnhancedJSONEncoder).encode(),
                    correlation_id=message.correlation_id,
                ),
                routing_key=message.reply_to,
            )
    
    async def send_to_DB(self, message):
        #send message to store
        await self.db_store_Exchange.publish(
            Message(
                body=json.dumps(message, cls=EnhancedJSONEncoder).encode(),
                content_type="application/json",
            ),
            routing_key="",
        )
