import asyncio
import logging
import websockets
import pika
import json
from chargePointRepr import ChargePoint

logging.basicConfig(level=logging.INFO)

def api_request(ch, method, properties, body):
    print("-----Received")
    print(body)

    print(properties.reply_to)

    ch.basic_publish(exchange='',
                     routing_key=properties.reply_to,
                     properties=pika.BasicProperties(correlation_id = \
                                                         properties.correlation_id),
                     body=str("response123"))

    ch.basic_ack(delivery_tag=method.delivery_tag)

    print("Response sent")

connection = pika.BlockingConnection(
    pika.ConnectionParameters('localhost'))
channel = connection.channel()

#Declare exchange
channel.exchange_declare(exchange='requests', exchange_type='topic')

#Declare queue
result = channel.queue_declare('Requests_Queue')
queue_name = result.method.queue

#Bind queue to exchange
channel.queue_bind(exchange='requests',
                   queue=queue_name,
                   routing_key='request.ocppserver')


#channel.basic_consume(
 #       queue=result, on_message_callback=api_request)



"""
async def on_connect(websocket, path):
    """""" For every new charge point that connects, create a ChargePoint
    instance and start listening for messages.
    """"""
    try:
        requested_protocols = websocket.request_headers[
            'Sec-WebSocket-Protocol']
    except KeyError:
        logging.info("Client hasn't requested any Subprotocol. "
                 "Closing Connection")
    if websocket.subprotocol:
        logging.info("Protocols Matched: %s", websocket.subprotocol)
    else:
        # In the websockets lib if no subprotocols are supported by the
        # client and the server, it proceeds without a subprotocol,
        # so we have to manually close the connection.
        logging.warning('Protocols Mismatched | Expected Subprotocols: %s,'
                        ' but client supports  %s | Closing connection',
                        websocket.available_subprotocols,
                        requested_protocols)
        return await websocket.close()

    charge_point_id = path.strip('/')
    cp = ChargePoint(charge_point_id, websocket)

    await cp.start()

    #TODO
    #create task to listen API
"""

async def main():
    """server = await websockets.serve(
        on_connect,
        '0.0.0.0',
        9000,
        subprotocols=['ocpp2.0.1']
    )
    logging.info("WebSocket Server Started")


    await server.wait_closed()"""
    channel.basic_consume(queue=queue_name, on_message_callback=api_request)

    channel.start_consuming()


if __name__ == '__main__':
    asyncio.run(main())
