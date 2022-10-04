from aio_pika import ExchangeType, Message, connect
import uuid
import json
import asyncio
from typing import MutableMapping

from aio_pika.abc import (
    AbstractChannel, AbstractConnection, AbstractIncomingMessage, AbstractQueue,
)

import dataclasses

class EnhancedJSONEncoder(json.JSONEncoder):
        def default(self, o):
            if dataclasses.is_dataclass(o):
                return dataclasses.asdict(o)
            return super().default(o)
            

class API_Rabbit_Handler:

    def __init__(self):

        #map of key: request_id, value: future
        # futures are async objects that will have a value in the future        
        self.futures: MutableMapping[str, asyncio.Future] = {}

        self.loop = asyncio.get_running_loop()

    
    async def connect(self):
        """
        connect to the rabbitmq server and setup connection
        """

        #Declare connection
        self.connection = await connect(
            "amqp://guest:guest@localhost/", loop=self.loop,
        )

        #declare channel
        self.channel = await self.connection.channel()

        #declare exchange to which the requests will be sent
        self.request_Exchange = await self.channel.declare_exchange(name="requests", type=ExchangeType.TOPIC)

        #declare a callback queue to where the reponses will be consumed
        self.callback_queue = await self.channel.declare_queue(exclusive=True)

        #consume messages from the queue
        await self.callback_queue.consume(self.on_response)

        return self


    def on_response(self, message: AbstractIncomingMessage) -> None:
        """
        callback funtion. Will be executed when a message is received in the callback queue
        """
        if message.correlation_id is None:
            print(f"Bad message {message!r}")
            return

        #get the future with key = correlationid
        future: asyncio.Future = self.futures.pop(message.correlation_id)
        
        #set a result to that future
        future.set_result(json.loads(message.body.decode()))
        

    
    async def send_get_request(self, message):
        """
        Send a request
        """

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
            routing_key="request.ocppserver",
        )

        #wait for the future to have a value and then return it
        return str(await future)