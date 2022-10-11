import asyncio
from db_Rabbit_Handler import DB_Rabbit_Handler
from aio_pika.abc import AbstractIncomingMessage
import logging
logging.basicConfig(level=logging.INFO)


async def on_api_request( message: AbstractIncomingMessage) -> None:
    logging.info("REQUEST - %s", str(message))

async def on_log( message: AbstractIncomingMessage) -> None:
    logging.info("STORE - %s", str(message))


async def main():
    broker = DB_Rabbit_Handler(on_api_request, on_log)

    await broker.connect()



if __name__ == '__main__':
    # Main part
    loop = asyncio.get_event_loop()

    loop.create_task(main())
    loop.run_forever()