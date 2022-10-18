import asyncio
from itertools import chain
from db_Rabbit_Handler import DB_Rabbit_Handler
from aio_pika.abc import AbstractIncomingMessage
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import db_Tables

logging.basicConfig(level=logging.INFO)

class DataBase:

    def __init__(self):

        #Initialize broker that will handle Rabbit coms
        self.broker = DB_Rabbit_Handler(self.on_api_request, self.on_log)

        #MySql engine
        self.engine = create_engine("mysql+pymysql://root:password123@localhost:3306/csms_db")

        #Create SQL tables
        db_Tables.create_Tables(self.engine)

        #Create new sqlachemy session
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        #map incoming messages to methods
        self.method_mapping={
            "BootNotification" : self.BootNotification
        }


    async def on_api_request(self, message: AbstractIncomingMessage) -> None:
        """
        Function that will handle incoming requests from the api or ocpp Server
        """

        logging.info("REQUEST - %s", str(message))


    async def on_log(self, message: AbstractIncomingMessage) -> None:
        """
        Function that will handle icoming messages to store information in the database
        """

        logging.info("STORE - %s", str(message))

        #call method depending on the message
        self.method_mapping[message["METHOD"]](message=message)

        #commit changes to the database
        self.session.commit()


    async def run(self):
        #Start listening to messages
        await self.broker.connect()



    def BootNotification(self, message):
        
        #Handles the creation of new chargepoints 
        
        charge_point_InMessage = message["CONTENT"]["charging_station"]

        if "modem" in charge_point_InMessage:
            if "iccid" in charge_point_InMessage["modem"]:
                charge_point_InMessage["modem_iccid"] = charge_point_InMessage["modem"]["iccid"]
            if "imsi" in charge_point_InMessage["modem"]:
                charge_point_InMessage["modem_imsi"] = charge_point_InMessage["modem"]["imsi"]
            
            charge_point_InMessage.pop('modem', None)

        charge_point = db_Tables.Charge_Point(**charge_point_InMessage)

        self.session.add(charge_point)




if __name__ == '__main__':
    # Main part
    loop = asyncio.new_event_loop()

    loop.create_task(DataBase().run())
    loop.run_forever()