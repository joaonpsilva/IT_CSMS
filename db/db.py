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
            "TransactionEvent" : self.TransactionEvent,
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
            result = id_token_info.get_dict_obj()

            allowed_evse = id_token_info.get_allowed_evse_for_cp(cp_id)                
            #check if not allowed for whole cp
            if len(allowed_evse) != 0 and len(allowed_evse) != len(self.session.query(db_Tables.Charge_Point).get({"cp_id" : cp_id})):
                result["evse_id"] = allowed_evse

        response = {
            "METHOD" : "AuthorizeResponse",
            "CP_ID" : cp_id,
            "CONTENT" : result
        }

        return response
    

    def TransactionEvent(self, cp_id, content):

        #pass common transaction info to transaction object
        if "id_token" in content:
            content["transaction_info"]["id_token"] = content["id_token"]
            content.pop("id_token")

        if "evse" in content:
            content["transaction_info"]["evse"] = content["evse"]
            content.pop("evse")
            
            if "connector_id" in content["transaction_info"]["evse"]:
                content["transaction_info"]["connector_id"] = content["transaction_info"]["evse"]["connector_id"]
                content["transaction_info"]["evse"].pop("connector_id")
        
        transaction_message = db_Tables.Transaction_Message(**content)
        self.session.merge(transaction_message)




if __name__ == '__main__':
    # Main part
    loop = asyncio.new_event_loop()

    loop.create_task(DataBase().run())
    loop.run_forever()