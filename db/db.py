import asyncio
from itertools import chain
from db_Rabbit_Handler import DB_Rabbit_Handler
from aio_pika.abc import AbstractIncomingMessage
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import exists
import db_Tables
from sqlalchemy.orm.util import identity_key


logging.basicConfig(level=logging.INFO)

class DataBase:

    def __init__(self):

        #Initialize broker that will handle Rabbit coms
        self.broker = DB_Rabbit_Handler(self.on_api_request, self.on_log)

        #MySql engine
        self.engine = create_engine("mysql+pymysql://root:password123@localhost:3306/csms_db")
        logging.info("Connected to the database")

        #Create SQL tables
        db_Tables.create_Tables(self.engine)

        #Create new sqlachemy session
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        #map incoming messages to methods
        self.method_mapping={
            "BootNotification" : self.BootNotification,
            "StatusNotification" : self.StatusNotification
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
        #try:
        self.session.commit()
        #except:
        #    logging.error("Error commiting changes to the database")


    async def run(self):
        #Start listening to messages
        await self.broker.connect()

        logging.info("Connected to the RMQ Broker")



    def BootNotification(self, message):
        
        #Handles the creation of new chargepoints 
        
        charge_point_InMessage = message["CONTENT"]["charging_station"]

        if "modem" in charge_point_InMessage:
            if "iccid" in charge_point_InMessage["modem"]:
                charge_point_InMessage["modem_iccid"] = charge_point_InMessage["modem"]["iccid"]
            if "imsi" in charge_point_InMessage["modem"]:
                charge_point_InMessage["modem_imsi"] = charge_point_InMessage["modem"]["imsi"]
            
            charge_point_InMessage.pop('modem', None)

        charge_point = db_Tables.Charge_Point(id= message["CP_ID"], **charge_point_InMessage)

        self.session.add(charge_point)
    

    def StatusNotification(self, message):
        
        #check if evse is already in DB
        q = self.session.query(db_Tables.EVSE.evse_id)\
        .filter(db_Tables.EVSE.evse_id==message["CONTENT"]["evse_id"])\
        .filter(db_Tables.EVSE.cp_id==message["CP_ID"])

        exists = self.session.query(q.exists()).scalar()

        #If not exists, insert
        if not exists:
            evse = db_Tables.EVSE(
                evse_id = message["CONTENT"]["evse_id"] , 
                cp_id= message["CP_ID"]
            )
            self.session.add(evse)

        #Insert connector
        connector = db_Tables.Connector(
            cp_id=message["CP_ID"],
            connector_id = message["CONTENT"]["connector_id"], 
            connector_status = message["CONTENT"]["connector_status"],
            evse_id = message["CONTENT"]["evse_id"]
        )
        
        self.session.add(connector)





if __name__ == '__main__':
    # Main part
    loop = asyncio.new_event_loop()

    loop.create_task(DataBase().run())
    loop.run_forever()