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


#UPDATE example
"""stmt = (
    update(db_Tables.Charge_Point).
    where(db_Tables.Charge_Point.cp_id == cp_id).
    values(**charge_point_InMessage)
)

self.session.execute(stmt)"""

#CHECK if exists
"""q = self.session.query(db_Tables.EVSE)\
    .filter(db_Tables.EVSE.evse_id==content["evse_id"])\
    .filter(db_Tables.EVSE.cp_id==cp_id)

exists = self.session.query(q.exists()).scalar()
"""

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
    
    def get_dict_obj(self, obj):
        return { attr:value for attr, value in obj.__dict__.items() if not attr.startswith("_") and value is not None }



    def verify_password(self, cp_id, content):
        charge_point = self.session.query(db_Tables.Charge_Point).get(cp_id)

        result = False
        if charge_point is not None:
            result = charge_point.verify_password(content["password"])
        
        response = {
            "METHOD" : "VERIFY_PASSWORD",
            "CP_ID" : cp_id,
            "CONTENT" : {
                "APPROVED" : result
            }
        }

        return response


    def BootNotification(self, cp_id, content):
                
        charge_point_InMessage = content["charging_station"]
        charge_point_InMessage["cp_id"] = cp_id

        cp = db_Tables.Charge_Point(**charge_point_InMessage)
        self.session.merge(cp)


    def StatusNotification(self, cp_id, content):

        content["cp_id"] = cp_id
        connector = db_Tables.Connector(**content)
        self.session.merge(connector)
        

    def MeterValues(self, cp_id, content): 
        
        evse_id = content["evse_id"]

        for meter_value_dict in content["meter_value"]:

            meter_value_dict["cp_id"] = cp_id
            meter_value_dict["evse_id"] = evse_id

            meter_value = db_Tables.MeterValue(**meter_value_dict)
            self.session.add(meter_value)
    

    def Authorize(self, cp_id, content):

        idToken = self.session.query(db_Tables.IdToken).get(content['id_token']['id_token'])

        result = None
        if idToken is not None:

            #get id token info
            id_token_info = idToken.id_token_info 
            
            #add available information
            result = self.get_dict_obj(id_token_info)

            #check if belongs to a group
            if id_token_info.group_id_token is not None:
                result["group_id_token"] = self.get_dict_obj(id_token_info.group_id_token)
            
            #check if has evse restrictions
            if len(id_token_info.evse) > 0:
                
                #get evse in which can charge in this cp
                allowed_evse = [evse.evse_id for evse in id_token_info.evse if evse.cp_id == cp_id]
                
                #check if not allowed for whole cp
                if len(allowed_evse) != len(self.session.query(db_Tables.Charge_Point).get({"cp_id" : cp_id})):
                    result["evse_id"] = allowed_evse

        response = {
            "METHOD" : "AuthorizeResponse",
            "CP_ID" : cp_id,
            "CONTENT" : result
        }

        return response




if __name__ == '__main__':
    # Main part
    loop = asyncio.new_event_loop()

    loop.create_task(DataBase().run())
    loop.run_forever()