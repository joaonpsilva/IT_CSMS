import asyncio
from db_Rabbit_Handler import DB_Rabbit_Handler
from aio_pika.abc import AbstractIncomingMessage


async def on_api_request(self, message: AbstractIncomingMessage) -> None:
    pass

async def on_log(self, message: AbstractIncomingMessage) -> None:
    pass


async def main():
    broker = DB_Rabbit_Handler()

    await broker.connect(on_api_request, on_log)



if __name__ == '__main__':
    asyncio.run(main())