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
from ocpp.v201 import enums
from datetime import datetime



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
            "Authorize_IdToken" : self.Authorize_IdToken,
            "TransactionEvent" : self.TransactionEvent,
            "VERIFY_PASSWORD" : self.verify_password,
            "VERIFY_RECEIVED_ALL_TRANSACTION" : self.verify_received_all_transaction

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
    
    def build_response(self, method, content, cp_id):
        message = {
            "METHOD" : method + "_RESPONSE",
            "CP_ID" : cp_id,
            "CONTENT" : content
        }
        return message



    def verify_password(self, cp_id, content, method = "VERIFY_PASSWORD"):
        charge_point = self.session.query(db_Tables.Charge_Point).get(cp_id)

        result = False
        if charge_point is not None:
            result = charge_point.verify_password(content["password"])

        return self.build_response(method, {"APPROVED" : result}, cp_id)



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

    
    def build_idToken_Info(self, idToken, cp_id, evse_id = None):
        """
        Builds an idTokenInfo based on id token
        """

        #no auth required
        if idToken["type"] == enums.IdTokenType.no_authorization:
            return {"status" : enums.AuthorizationStatusType.accepted}


        try:
            idToken_fromDb = self.session.query(db_Tables.IdToken).get(idToken["id_token"])
            assert(idToken_fromDb.type == idToken["type"])
        except:
            return {"status" : enums.AuthorizationStatusType.invalid}

        if idToken_fromDb is not None:

            #get id token info
            id_token_info = idToken_fromDb.id_token_info 
            
            #add available information
            result = id_token_info.get_dict_obj()

            allowed_evse = id_token_info.get_allowed_evse_for_cp(cp_id)                
            #check if not allowed for whole cp
            if len(allowed_evse) != len(self.session.query(db_Tables.Charge_Point).get(cp_id).evse):
                result["evse_id"] = allowed_evse
            

            #--------Choose STATUS

            if id_token_info.cache_expiry_date_time != None and id_token_info.cache_expiry_date_time < datetime.utcnow().isoformat():
                result["status"] = enums.AuthorizationStatusType.expired
            elif len(allowed_evse) == 0 or (evse_id is not None and evse_id not in allowed_evse):
                #in authorize request, cant know this because dont know the evse
                result["status"] = enums.AuthorizationStatusType.not_at_this_location
            else: 
                result["status"] = enums.AuthorizationStatusType.accepted
        
        else:
            result = {"status" : enums.AuthorizationStatusType.unknown}

        
        return result
    
            

    def Authorize_IdToken(self, cp_id, content, method="Authorize_IdToken"):
        """cannot deal with certificates yet"""
        #validate idtoken
        id_token_info = self.build_idToken_Info(
            content['id_token'],
            cp_id,
            content['evse_id'] if 'evse_id' in content else None)

        return self.build_response(method, {"id_token_info" : id_token_info}, cp_id)
    

    def verify_received_all_transaction(self, cp_id, content, method="VERIFY_RECEIVED_ALL_TRANSACTION"):
        
        response = {"status" : "OK"}
        try:
            assert("transaction_id" in content)
            
            transaction = self.session.query(db_Tables.Transaction).get(content["transaction_id"])
            assert(transaction is not None)

            transaction_events = sorted(transaction.transaction_event, key=lambda t : t.seq_no)
            assert(transaction_events[0].event_type == enums.TransactionEventType.started)

            if transaction_events[-1].event_type != enums.TransactionEventType.ended or\
                transaction_events[-1].seq_no - transaction_events[0].seq_no > len(transaction_events)-1:
                response["status"] = "MISSING_MESSAGES"
        except:
            response["status"] = "ERROR"

        return self.build_response(method, response, cp_id)
        


    def TransactionEvent(self, cp_id, content):

        #TODO check if is oldest message for transaction, if not, dont update transaction info
        
        #If message contains idtoken
        if "id_token" in content:

            q = self.session.query(db_Tables.IdToken).filter(db_Tables.IdToken.id_token==content["id_token"]["id_token"])
            exists = self.session.query(q.exists()).scalar()
                
            #if for some reason, this idtoken is not good, dont use it to store in db
            if not exists:
                content.pop("id_token")


        if "evse" in content:
            content["evse"]["cp_id"] = cp_id
            if "connector_id" in content["evse"]:
                content["connector"] = content.pop("evse")
        else:
            content["cp_id"] = cp_id
        
        #introduce message in DB
        transaction_event = db_Tables.Transaction_Event(**content)
        self.session.merge(transaction_event)


if __name__ == '__main__':
    # Main part
    loop = asyncio.new_event_loop()

    loop.create_task(DataBase().run())
    loop.run_forever()