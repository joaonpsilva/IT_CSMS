from aio_pika import ExchangeType, Message, connect

from rabbit_mq.rabbit_handler import Rabbit_Handler, Fanout_Message

import logging
logging.basicConfig(level=logging.INFO)


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
        self.request_queue = await self.channel.declare_queue(self.name + "_Request_queue")
        #Bind queue to exchange so that the queue is eligible to receive requests
        await self.request_queue.bind(self.exchange, routing_key='')
        #Start consuming requests from the queue
        await self.request_queue.consume(self.on_request, no_ack=False)


        #declare a callback queue to where the reponses will be consumed
        self.response_queue = await self.channel.declare_queue(self.name + "_Response_queue")
        #Bind queue to exchange so that the queue is eligible to receive responses
        await self.response_queue.bind(self.exchange, routing_key='')
        #consume messages from the queue
        await self.response_queue.consume(self.on_response, no_ack=False)

        logging.info(self.name + " Connected to the RMQ Broker")