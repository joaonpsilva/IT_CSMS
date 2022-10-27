import asyncio
from itertools import chain
from db_Rabbit_Handler import DB_Rabbit_Handler
from aio_pika.abc import AbstractIncomingMessage
import logging
from sqlalchemy import create_engine, update
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import exists
import db_Tables
from sqlalchemy.orm.util import identity_key


logging.basicConfig(level=logging.INFO)

class DataBase:

    def __init__(self):

        #MySql engine
        self.engine = create_engine("mysql+pymysql://root:password123@localhost:3306/csms_db")
        logging.info("Connected to the database")

        #Create new sqlachemy session
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        #Create SQL tables
        db_Tables.create_Tables(self.engine)

        #Insert some CPs (testing)
        db_Tables.insert_Hard_Coded(self)


        #map incoming messages to methods
        self.method_mapping={
            "BootNotification" : self.BootNotification,
            "StatusNotification" : self.StatusNotification,
            "MeterValues" : self.MeterValues,
            "Authorize" : self.Authorize,
            "VERIFY_PASSWORD" : self.verify_password

        }


    async def on_db_request(self, message: AbstractIncomingMessage) -> None:
        """
        Function that will handle incoming requests from the api or ocpp Server
        """

        #call method depending on the message
        toReturn = self.method_mapping[message["METHOD"]](cp_id = message['CP_ID'], content = message['CONTENT'])
        
        #commit possible changes
        self.session.commit()

        return toReturn

    # async def on_log(self, message: AbstractIncomingMessage) -> None:
    #     """
    #     Function that will handle icoming messages to store information in the database
    #     """

    #     #call method depending on the message
    #     self.method_mapping[message["METHOD"]](message)
    #     self.session.commit()



    async def run(self):

        #Initialize broker that will handle Rabbit coms
        self.broker = DB_Rabbit_Handler(self.on_db_request)
        #Start listening to messages
        await self.broker.connect()

    def get_class_attributes(self, c):
        return [attr for attr in dir(c) if not callable(getattr(c, attr)) and not attr.startswith("_")]


    def verify_password(self, cp_id, content):
        charge_point = self.session.query(db_Tables.Charge_Point).get(cp_id)

        result = False
        if charge_point is not None:
            result = charge_point.verify_password(content["password"])
        
        response = {
            "METHOD" : "VERIFY_PASSWORD",
            "CP_ID" : cp_id,
            "PASSWORD" : content["password"],
            "APPROVED" : result
        }

        return response




    def BootNotification(self, cp_id, content):
                
        charge_point_InMessage = content["charging_station"]

        if "modem" in charge_point_InMessage:
            if "iccid" in charge_point_InMessage["modem"]:
                charge_point_InMessage["modem_iccid"] = charge_point_InMessage["modem"]["iccid"]
            if "imsi" in charge_point_InMessage["modem"]:
                charge_point_InMessage["modem_imsi"] = charge_point_InMessage["modem"]["imsi"]
            
            charge_point_InMessage.pop('modem', None)

        stmt = (
            update(db_Tables.Charge_Point).
            where(db_Tables.Charge_Point.id == cp_id).
            values(**charge_point_InMessage)
        )

        self.session.execute(stmt)  



    def StatusNotification(self, cp_id, content):
        
        #------------check if EVSE is already in DB
        q = self.session.query(db_Tables.EVSE)\
            .filter(db_Tables.EVSE.evse_id==content["evse_id"])\
            .filter(db_Tables.EVSE.cp_id==cp_id)

        exists = self.session.query(q.exists()).scalar()

        if not exists:
            #If not exists, insert
            evse = db_Tables.EVSE(
                evse_id = content["evse_id"] , 
                cp_id= cp_id
            )
            self.session.add(evse)

        #------------check if connector exists
        q = self.session.query(db_Tables.Connector)\
            .filter(db_Tables.Connector.connector_id==content["connector_id"])\
            .filter(db_Tables.Connector.evse_id==content["evse_id"])\
            .filter(db_Tables.Connector.cp_id==cp_id)
        
        exists = self.session.query(q.exists()).scalar()

        if not exists:
            #Insert connector
            connector = db_Tables.Connector(
                cp_id=cp_id,
                connector_id = content["connector_id"], 
                connector_status = content["connector_status"],
                evse_id = content["evse_id"]
            )
            
            self.session.add(connector)
        else:
            #update status
            q.update({'connector_status': content["connector_status"]})



    def MeterValues(self, cp_id, content): 
        
        evse_id = content["evse_id"]

        for meter_value in content["meter_value"]:
            timestamp = meter_value["timestamp"]

            for sampled_value in meter_value["sampled_value"]:
                filtered_sampled_value = {key: value for key, value in sampled_value.items() if key in self.get_class_attributes(db_Tables.MeterValue)}
                
                meter_value_obj = db_Tables.MeterValue(
                    cp_id=cp_id,
                    evse_id=evse_id,
                    timestamp=timestamp,
                    **filtered_sampled_value)
                
                self.session.add(meter_value_obj)
    

    def Authorize(self, cp_id, content):

        idToken = self.session.query(db_Tables.IdToken).get(content['id_token']['id_token'])
        if idToken is None:


        response = {
            "METHOD" : "Authorize",
            "CP_ID" : cp_id,
            "APPROVED" : result
        }

        return response




if __name__ == '__main__':
    # Main part
    loop = asyncio.new_event_loop()

    loop.create_task(DataBase().run())
    loop.run_forever()