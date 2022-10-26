import dataclasses
from aio_pika import ExchangeType, Message, connect
import json
import asyncio
import uuid
from typing import MutableMapping
from aio_pika.abc import (
    AbstractChannel, AbstractConnection, AbstractIncomingMessage, AbstractQueue,
)
import logging

class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)

class Rabbit_Handler:


    def __init__(self, handle_request = None):

        #map of key: request_id, value: future
        #futures are async objects that will have a value in the future        
        self.futures: MutableMapping[str, asyncio.Future] = {}
        self.loop = asyncio.get_running_loop()

        self.handle_request = handle_request

    
    async def connect(self, create_response_queue = True):
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

        if create_response_queue:
            #declare a callback queue to where the reponses will be consumed
            self.callback_queue = await self.channel.declare_queue(exclusive=True)
            #consume messages from the queue
            await self.callback_queue.consume(self.on_response)
        
        logging.info("Connected to the RMQ Broker")


            
    def on_response(self, message: AbstractIncomingMessage) -> None:
        """
        callback funtion. Will be executed when a message is received in the callback queue
        """
        logging.info("RabbitMQ RECEIVED response: %s", str(json.loads(message.body.decode())))

        if message.correlation_id is None:
            logging.info(f"Bad response {message!r}")
            return

        #get the future with key = correlationid
        future: asyncio.Future = self.futures.pop(message.correlation_id)
        
        #set a result to that future
        future.set_result(json.loads(message.body.decode()))


    async def unpack(self, message: AbstractIncomingMessage):
        #manually acknowledge
        await message.ack()

        #load json content
        return json.loads(message.body.decode())


    async def on_request(self, message: AbstractIncomingMessage) -> None:
        """Received message from with a request"""

        #load json content
        content = await self.unpack(message)

        logging.info("RabbitMQ RECEIVED request: %s", str(content))

        #pass content to csms
        response = await self.handle_request(content)
        
        #send response to the api if requested
        if message.reply_to is not None:
            logging.info("RabbitMQ REPLYING: %s", str(response))
            await self.channel.default_exchange.publish(
                Message(
                    body=json.dumps(response, cls=EnhancedJSONEncoder).encode(),
                    correlation_id=message.correlation_id,
                ),
                routing_key=message.reply_to,
            )
        
    async def send_request_wait_response(self, message, routing_key):
        """
        Send a request and wait for response
        """

        logging.info("RabbitMQ SENDING request: %s", str(message))

        #create an ID for the request
        requestID = str(uuid.uuid4())

        #create a future and introduce it in the request map
        future = self.loop.create_future()
        self.futures[requestID] = future

        #send request
        await self.request_Exchange.publish(
            Message(
                body=json.dumps(message, cls=EnhancedJSONEncoder).encode(),
                content_type="application/json",
                correlation_id=requestID,
                reply_to=self.callback_queue.name,  #tell consumer: reply to this queue
            ),
            routing_key=routing_key,
        )

        #wait for the future to have a value and then return it
        try:
            return await asyncio.wait_for(future, timeout=5)
        except asyncio.TimeoutError:
            #maybe delete entry in future map?
            return "ERROR"
    
    
    async def send_to_DB(self, message):

        logging.info("RabbitMQ SENDING info to store: %s", str(message))

        #send message to store
        await self.db_store_Exchange.publish(
            Message(
                body=json.dumps(message, cls=EnhancedJSONEncoder).encode(),
                content_type="application/json",
            ),
            routing_key="",
        )