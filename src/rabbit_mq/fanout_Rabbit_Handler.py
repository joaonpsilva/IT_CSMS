from aio_pika import ExchangeType, Message, connect

from rabbit_mq.rabbit_handler import Rabbit_Handler, Fanout_Message
from aio_pika.abc import AbstractIncomingMessage

import logging
logging.basicConfig(level=logging.INFO)
import json

class Fanout_Rabbit_Handler(Rabbit_Handler):
    """class that will handle communication inter services"""

    def __init__(self, name, handle_request = None):
        super().__init__(name, handle_request)
        self.rabbit_Message = Fanout_Message

    
    async def connect(self, url):
        """
        connect to the rabbitmq server and setup connection
        """

        #Declare connection
        self.connection = await connect(url)

        #declare channel
        self.channel = await self.connection.channel()

        #TODO exchanges?
        self.exchange = await self.channel.declare_exchange(name="fanout", type=ExchangeType.FANOUT)

        #Declare queue that will receive the requests to be handled by the occp_server
        self.request_queue = await self.channel.declare_queue(self.name + "_Queue")
        #Bind queue to exchange so that the queue is eligible to receive requests
        await self.request_queue.bind(self.exchange, routing_key='')
        #Start consuming requests from the queue
        await self.request_queue.consume(self.on_message, no_ack=False)


        logging.info(self.name + " Connected to the RMQ Broker")

    
    async def on_message(self, message: AbstractIncomingMessage):
        m = self.rabbit_Message(**json.loads(message.body.decode()))

        if m.type == "response":
            await self.on_response(message)
        elif m.type == "request":
            await self.on_request(message)