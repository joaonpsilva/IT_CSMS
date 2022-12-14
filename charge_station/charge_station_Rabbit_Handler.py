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
from rabbit_handler import Rabbit_Handler, EnhancedJSONEncoder

import logging
logging.basicConfig(level=logging.INFO)


class Charge_Station_Rabbit_Handler(Rabbit_Handler):
    """class that will handle communication inter services"""

    
    async def connect(self):
        """
        connect to the rabbitmq server and setup connection
        """

        #Declare connection
        self.connection = await connect("amqp://guest:guest@localhost/")

        #declare channel
        self.channel = await self.connection.channel()

        #TODO exchanges?
        self.private_Exchange = await self.channel.declare_exchange(name="messages", type=ExchangeType.TOPIC)


        #declare a callback queue to where the reponses will be consumed
        self.callback_queue = await self.channel.declare_queue("ocpp_client_response_queue")
        #Bind queue to exchange so that the queue is eligible to receive responses
        await self.request_queue.bind(self.channel.default_exchange, routing_key='ocpp_client.response')
        #consume messages from the queue
        await self.callback_queue.consume(self.on_response)


        #Declare queue that will receive the requests to be handled by the occp_server
        self.request_queue = await self.channel.declare_queue("ocpp_client_request_queue")
        #Bind queue to exchange so that the queue is eligible to receive requests
        await self.request_queue.bind(self.channel.default_exchange, routing_key='ocpp_client.request')
        #Start consuming requests from the queue
        await self.request_queue.consume(self.on_request, no_ack=False)

        logging.info("Connected to the RMQ Broker")
    
    async def on_response(self, message: AbstractIncomingMessage) -> None:
        """
        callback funtion. Will be executed when a message is received in the callback queue
        """
        logging.info("RabbitMQ RECEIVED response: %s", str(json.loads(message.body.decode())))

        if message.correlation_id is None:
            message.correlation_id = "OCPP"

        #get the future with key = correlationid
        future: asyncio.Future = self.futures.pop(message.correlation_id)

        #set a result to that future
        future.set_result(json.loads(message.body.decode())["content"])

    

    async def send_request_wait_response(self, message):
        """
        Send a request and wait for response
        """
        message.type = "REQUEST"

        if message.destination == "decision_point":
            requestID = "OCPP"
        else:
            #create an ID for the request
            requestID = str(uuid.uuid4())

        #create a future and introduce it in the request map
        future = self.loop.create_future()
        self.futures[requestID] = future

        #send request
        await self.send_Message(message, requestID, self.callback_queue.name)

        #wait for the future to have a value and then return it
        try:
            return await asyncio.wait_for(future, timeout=5)
        except asyncio.TimeoutError:
            self.futures.pop(requestID)
            logging.error("No response received")
            return {"status":"ERROR"}
    

        

    



