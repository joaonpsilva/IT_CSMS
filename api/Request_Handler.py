import pika
import uuid
import json
import queue

class Request_Handler:

    def __init__(self):
        
        #Declare channel
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='localhost'))
        self.channel = self.connection.channel()

        #Declare exchange
        self.channel.exchange_declare(exchange='requests', exchange_type='topic')

        #Declare a queue for the responses
        self.response_queue = self.channel.queue_declare(queue='', exclusive=True)
        self.response_queue_name = self.response_queue.method.queue

        
        #Initiate consumer on the response queue
        

        
        self.waiting_Requests={}
    
    async def init_Consumer(self):
        #self.response_queue.consume(self.on_response, no_ack=True)
        self.channel.basic_consume(
            queue=self.response_queue_name,
            on_message_callback=self.on_response,
            auto_ack=True)
        
        self.channel.start_consuming()
    

    def on_response(self, ch, method, props, body):

        print("received somthing")

        self.waiting_Requests[props.correlation_id].put(body)

    
    def call(self, message):

        requestID = str(uuid.uuid4())

        self.waiting_Requests[requestID] = queue.Queue()


        self.channel.basic_publish(
            exchange='requests',
            routing_key='request.ocppserver',
            properties=pika.BasicProperties(
                reply_to=self.response_queue_name,
                correlation_id=requestID,
            ),
            body=json.dumps(message))
        
        try:
            return self.waiting_Requests[requestID].get(timeout=5)
        except Exception:
            
            print("Giving up")