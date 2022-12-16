import asyncio

from charge_station_Rabbit_Handler import Charge_Station_Rabbit_Handler
#TODO needs own queue

class DataBase_CP:

    async def on_db_request(self, message):
        print(message)


    async def run(self):

        #Initialize broker that will handle Rabbit coms
        self.broker = Charge_Station_Rabbit_Handler(self.on_db_request)
        #Start listening to messages
        await self.broker.connect()



if __name__ == '__main__':
    # Main part
    loop = asyncio.new_event_loop()

    loop.create_task(DataBase_CP().run())
    loop.run_forever()