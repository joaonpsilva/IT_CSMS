import asyncio

import sys
from os import path
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
from fanout_Rabbit_Handler import Fanout_Rabbit_Handler

class DataBase_CP:

    async def on_db_request(self, message):
        print(message)


    async def run(self):

        #Initialize broker that will handle Rabbit coms
        self.broker = Fanout_Rabbit_Handler(self.on_db_request, "OCPPclientDB")
        #Start listening to messages
        await self.broker.connect()



if __name__ == '__main__':
    # Main part
    loop = asyncio.new_event_loop()

    loop.create_task(DataBase_CP().run())
    loop.run_forever()