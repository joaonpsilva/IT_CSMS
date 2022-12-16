import sys
from aio_pika import ExchangeType, Message, connect
import asyncio
import uuid
import json
from aio_pika.abc import (
    AbstractChannel, AbstractConnection, AbstractIncomingMessage, AbstractQueue,
)
from os import path
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
from rabbit_handler import Rabbit_Handler, EnhancedJSONEncoder, Rabbit_Message

import logging
logging.basicConfig(level=logging.INFO)


class Fanout_Message(Rabbit_Message):
    def __init__(self, intent = None, type = None,content = None):
        self.intent = intent
        self.type = type
        self.content = content
    
    def routing_key(self):
        return ''
    
    def prepare_Response(self):
        self.type = "RESPONSE"
        self.content = None
        return self


class Charge_Station_Rabbit_Handler(Rabbit_Handler):
    """class that will handle communication inter services"""

    def __init__(self, handle_request = None):
        super().__init__(handle_request)
        self.rabbit_Message = Fanout_Message

    
    async def connect(self):
        """
        connect to the rabbitmq server and setup connection
        """

        #Declare connection
        self.connection = await connect("amqp://guest:guest@localhost/")

        #declare channel
        self.channel = await self.connection.channel()

        #TODO exchanges?
        self.fanout_Exchange = await self.channel.declare_exchange(name="fanout", type=ExchangeType.FANOUT)


        #Declare queue that will receive the requests to be handled by the occp_server
        self.request_queue = await self.channel.declare_queue("ocpp_client_request_queue")
        #Bind queue to exchange so that the queue is eligible to receive requests
        await self.request_queue.bind(self.fanout_Exchange, routing_key='')
        #Start consuming requests from the queue
        await self.request_queue.consume(self.on_request, no_ack=False)


        #declare a callback queue to where the reponses will be consumed
        self.callback_queue = await self.channel.declare_queue("ocpp_client_response_queue")
        #Bind queue to exchange so that the queue is eligible to receive responses
        await self.callback_queue.bind(self.fanout_Exchange, routing_key='')
        #consume messages from the queue
        await self.callback_queue.consume(self.on_response, no_ack=False)

        logging.info("Connected to the RMQ Broker")
    
    

    async def ocpp_log(self, message):
        message.type = "REQUEST"
        await self.send_Message(message, exange=self.fanout_Exchange)