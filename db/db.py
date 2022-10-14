import asyncio
from db_Rabbit_Handler import DB_Rabbit_Handler
from aio_pika.abc import AbstractIncomingMessage
import logging
import mysql.connector

logging.basicConfig(level=logging.INFO)

class DataBase:

    def __init__(self):
        self.broker = DB_Rabbit_Handler(self.on_api_request, self.on_log)

        self.db = mysql.connector.connect(
            host="localhost",
            user="root",
            passwd="password123"
        )
        self.cursor = self.db.cursor()


    async def on_api_request(self, message: AbstractIncomingMessage) -> None:
        logging.info("REQUEST - %s", str(message))

    async def on_log(self, message: AbstractIncomingMessage) -> None:
        logging.info("STORE - %s", str(message))


    async def run(self):
        await self.broker.connect()



if __name__ == '__main__':
    # Main part
    loop = asyncio.new_event_loop()

    loop.create_task(DataBase().run())
    loop.run_forever()