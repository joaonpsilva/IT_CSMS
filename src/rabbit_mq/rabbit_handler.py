import dataclasses
from aio_pika import ExchangeType, Message, connect
import json
import asyncio
import uuid
from typing import MutableMapping
from aio_pika.abc import AbstractIncomingMessage
import logging
import datetime

#SEE TODO
#https://stackoverflow.com/questions/53374144/rabbitmq-ack-timeout

class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        if isinstance(o, datetime.datetime):
            return o.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(o, Rabbit_Message):
            return o.__dict__
        return super().default(o)

class Rabbit_Message:
    def routing_key(self):
        raise NotImplementedError
    def prepare_Response(self):
        raise NotImplementedError


class Topic_Message(Rabbit_Message):
    def __init__(self, destination = None, origin = None, method = None,type = None,content = None,cp_id = None):
        self.destination = destination
        self.origin = origin
        self.method = method
        self.type = type
        self.content = content
        self.cp_id = cp_id

    def routing_key(self):
        s=self.type
        if self.destination!=None:
            s += "." + self.destination
        if self.cp_id!=None:
            s += "." + self.cp_id
        return s

    def prepare_Response(self):
        temp_destination = self.destination
        self.destination = self.origin
        self.origin = temp_destination
        self.type = "response"
        self.content = None
        return self


class Fanout_Message(Rabbit_Message):
    def __init__(self, intent = None, type = None,content = None):
        self.intent = intent
        self.type = type
        self.content = content
    
    def routing_key(self):
        return ''
    
    def prepare_Response(self):
        self.type = "response"
        self.content = None
        return self
    

class Rabbit_Handler:

    def __init__(self, name, handle_request = None):

        #map of key: request_id, value: future
        #futures are async objects that will have a value in the future        
        self.futures: MutableMapping[str, asyncio.Future] = {}
        self.loop = asyncio.get_running_loop()

        self.rabbit_Message = Topic_Message

        self.handle_request = handle_request
        self.name = name
        self.logger = logging.getLogger(name)


    async def connect(self, url, receive_requests=True, receive_logs=True, receive_responses=True):
        """
        connect to the rabbitmq server and setup connection
        """

        #Declare connection
        self.connection = await connect(url)

        #declare channel
        self.channel = await self.connection.channel()

        #Declare exchange to where communication will be sent
        self.exchange = await self.channel.declare_exchange(name="messages", type=ExchangeType.TOPIC)

        if receive_requests or receive_logs:
            #Declare queue that will receive the requests or logs
            self.request_queue = await self.channel.declare_queue(self.name + "_Request_Queue")
            
            if receive_requests:
                #Bind queue to exchange so that the queue is eligible to receive requests
                await self.request_queue.bind(self.exchange, routing_key="request." + self.name + ".#")
            
            if receive_logs:
                await self.request_queue.bind(self.exchange, routing_key='ocpp_log.#')

            #Start consuming requests from the queue
            await self.request_queue.consume(self.on_request, no_ack=False)
        

        if receive_responses:
            #declare a callback queue to where the reponses will be consumed
            self.response_queue = await self.channel.declare_queue(self.name + "_Response_Queue", exclusive=True)
            await self.response_queue.bind(self.exchange, routing_key="response." + self.name + ".#")
            #consume messages from the queue
            await self.response_queue.consume(self.on_response)



        self.logger.info("Connected to the RMQ Broker")



    async def unpack(self, message: AbstractIncomingMessage):
        #manually acknowledge
        await message.ack()
        #load json content
        return self.rabbit_Message(**json.loads(message.body.decode()))

            
    async def on_response(self, message: AbstractIncomingMessage) -> None:
        """
        callback funtion. Will be executed when a message is received in the callback queue
        """

        #load json content
        response = await self.unpack(message)

        if response.type != "response":
            return
        
        if not message.correlation_id:
            message.correlation_id = response.intent

        #get the future with key = correlationid
        if message.correlation_id in self.futures:
            self.logger.info("RESPONSE: %s", response.__dict__)

            future: asyncio.Future = self.futures.pop(message.correlation_id)
            #set a result to that future
            future.set_result(response.content)



    async def on_request(self, message: AbstractIncomingMessage) -> None:
        """Received message from with a request"""

        #load json content
        request = await self.unpack(message)

        if request.type not in ["request", "ocpp_log"]:
            return

        self.logger.info("RECEIVED: %s", request.__dict__)

        #pass content to be handled
        response_content = await self.handle_request(request)
        
        #send response to the entity that made the request
        if request.type == "request" and response_content is not None:
            response = request.prepare_Response()
            response.content = response_content

            await self.send_Message(response, message.correlation_id)
            

        
    async def send_request_wait_response(self, message, timeout=5):
        """
        Send a request and wait for response
        """
        if isinstance(message, Topic_Message):
            message.origin = self.name
        message.type = "request"

        #create an ID for the request
        if isinstance(message, Fanout_Message):
            requestID = message.intent
        else:
            requestID = str(uuid.uuid4())

        #create a future and introduce it in the request map
        future = self.loop.create_future()
        self.futures[requestID] = future

        #send request
        await self.send_Message(message, requestID, self.response_queue.name)

        #wait for the future to have a value and then return it
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self.futures.pop(requestID)
            self.logger.info("No response received")
            raise TimeoutError
        

    async def ocpp_log(self, message):
        try:
            if isinstance(message, Topic_Message):
                message.origin = self.name
            message.type = "ocpp_log"
            await self.send_Message(message)
        except:
            return

    
    async def send_Message(self, message, requestID=None, reply_to=None, routing_key=None):
        json_message = json.dumps(message, cls=EnhancedJSONEncoder)
        self.logger.info("RabbitMQ SENDING Message: %s", str(json_message))
        
        await self.exchange.publish(
            Message(
                body=json_message.encode(),
                content_type="application/json",
                correlation_id=requestID,
                reply_to=reply_to,  #tell consumer: reply to this queue
            ),
            routing_key=routing_key if routing_key != None else message.routing_key(),
        )