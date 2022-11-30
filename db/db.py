import asyncio
from itertools import chain
from db_Rabbit_Handler import DB_Rabbit_Handler
from aio_pika.abc import AbstractIncomingMessage
import logging
from sqlalchemy import create_engine, update, select
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import exists, text
from db_Tables import *
from sqlalchemy.orm.util import identity_key
from ocpp.v201 import enums
from datetime import datetime

import dateutil.parser

logging.basicConfig(level=logging.INFO)


#UPDATE example
"""stmt = (
    update(Charge_Point).
    where(Charge_Point.cp_id == cp_id).
    values(**charge_point_InMessage)
)

self.session.execute(stmt)"""

#CHECK if exists
"""q = self.session.query(EVSE)\
    .filter(EVSE.evse_id==content["evse_id"])\
    .filter(EVSE.cp_id==cp_id)

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
        create_Tables(self.engine)

        #Insert some CPs (testing)
        insert_Hard_Coded(self)


        #map incoming messages to methods
        self.method_mapping={
            "BootNotification" : self.BootNotification,
            "StatusNotification" : self.StatusNotification,
            "MeterValues" : self.MeterValues,
            "Authorize" : self.Authorize_IdToken,
            "TransactionEvent" : self.TransactionEvent,
            "VERIFY_PASSWORD" : self.verify_password,
            "VERIFY_RECEIVED_ALL_TRANSACTION" : self.verify_received_all_transaction,
            "VERIFY_CHARGING_PROFILE_CONFLICTS" : self.verify_charging_profile_conflicts,
            "SetChargingProfile" : self.setChargingProfile,
            "clearChargingProfile" : self.delete_charging_profile,
            "GET_FROM_TABLE" : self.get_from_table
        }

        self.table_mapping={
            "Modem":Modem,
            "Charge_Point":Charge_Point,
            "EVSE":EVSE,
            "Connector":Connector,
            "MeterValue":MeterValue,
            "SignedMeterValue":SignedMeterValue,
            "SampledValue":SampledValue,
            "IdToken":IdToken,
            "GroupIdToken":GroupIdToken,
            "IdTokenInfo":IdTokenInfo,
            "Transaction":Transaction,
            "Transaction_Event":Transaction_Event,
            "ChargingProfile":ChargingProfile,
            "ChargingSchedule":ChargingSchedule,
            "EventData":EventData,
            }


    async def on_db_request(self, message: AbstractIncomingMessage):
        """
        Function that will handle incoming requests from the api or ocpp Server
        """
        try:
            #call method depending on the message
            method = message.pop("method")
            toReturn = self.method_mapping[method](**message)
            #commit possible changes
            self.session.commit()

            return {"status":"OK", "content":toReturn}
        except Exception as e:
            logging.error(e)
            return {"status":"ERROR"}


    async def run(self):

        #Initialize broker that will handle Rabbit coms
        self.broker = DB_Rabbit_Handler(self.on_db_request)
        #Start listening to messages
        await self.broker.connect()

    def get_class_attributes(self, c):
        return [attr for attr in dir(c) if not callable(getattr(c, attr)) and not attr.startswith("_")]
    
    def get_dict_obj(self, obj):
        return { attr:value for attr, value in obj.__dict__.items() if not attr.startswith("_") and value is not None }
    

    def get_from_table(self, content, cp_id=None):
        if "filters" not in content:
            content["filters"] = {}

        statement = select(self.table_mapping[content["table"]]).filter_by(**content["filters"])
        return [obj.get_dict_obj() for obj in self.session.scalars(statement).all()]


    def verify_password(self, cp_id, content):
        #TODO assert not already online
        charge_point = self.session.query(Charge_Point).get(cp_id)

        result = False
        if charge_point is not None:
            result = charge_point.verify_password(content["password"])

        return {"approved" : result}



    def BootNotification(self, cp_id, content):
                
        charge_point_InMessage = content["charging_station"]
        charge_point_InMessage["cp_id"] = cp_id

        cp = Charge_Point(**charge_point_InMessage)
        self.session.merge(cp)


    def StatusNotification(self, cp_id, content):

        evse = EVSE(cp_id=cp_id, evse_id=content["evse_id"])

        connector = Connector(cp_id=cp_id, **content, evse=evse)
        self.session.merge(connector)
        

    def MeterValues(self, cp_id, content): 
        
        evse_id = content["evse_id"]

        for meter_value_dict in content["meter_value"]:

            meter_value_dict["cp_id"] = cp_id
            meter_value_dict["evse_id"] = evse_id

            meter_value = MeterValue(**meter_value_dict)
            self.session.add(meter_value)

    
    def build_idToken_Info(self, idToken, cp_id, evse_id = None):
        """
        Builds an idTokenInfo based on id token
        """

        #no auth required
        if idToken["type"] == enums.IdTokenType.no_authorization:
            return {"status" : enums.AuthorizationStatusType.accepted}


        try:
            idToken_fromDb = self.session.query(IdToken).get(idToken["id_token"])
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
            if len(allowed_evse) != len(self.session.query(Charge_Point).get(cp_id).evse):
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
    
            

    def Authorize_IdToken(self, cp_id, content):
        """cannot deal with certificates yet"""
        #validate idtoken
        id_token_info = self.build_idToken_Info(
            content['id_token'],
            cp_id,
            content['evse_id'] if 'evse_id' in content else None)

        return {"id_token_info" : id_token_info}


    def verify_received_all_transaction(self, cp_id, content):
        
        response = {"status" : "OK"}
        try:
            assert("transaction_id" in content)
            
            transaction = self.session.query(Transaction).get(content["transaction_id"])
            assert(transaction is not None)

            transaction_events = sorted(transaction.transaction_event, key=lambda t : t.seq_no)
            assert(transaction_events[0].event_type == enums.TransactionEventType.started)

            if transaction_events[-1].event_type != enums.TransactionEventType.ended or\
                transaction_events[-1].seq_no - transaction_events[0].seq_no > len(transaction_events)-1:
                response["status"] = "MISSING_MESSAGES"
        except:
            response["status"] = "ERROR"

        return response



    def TransactionEvent(self, cp_id, content):
        
        #If message contains idtoken
        if "id_token" in content:
            #if for some reason, this idtoken is not good, dont use it to store in db

            q = self.session.query(IdToken).filter(IdToken.id_token==content["id_token"]["id_token"])
            exists = self.session.query(q.exists()).scalar()
            if not exists:
                content.pop("id_token")

        #introduce cp_id in message, decide if is EVSE or connector
        if "evse" in content:
            content["evse"]["cp_id"] = cp_id
            if "connector_id" in content["evse"]:
                content["evse"]["evse_id"] = content["evse"].pop("id")
                content["connector"] = content.pop("evse")
        else:
            content["cp_id"] = cp_id 

        #check if there is a more recent event. (Dont update transaction)
        transaction = self.session.query(Transaction).get(content["transaction_info"]["transaction_id"])
        if transaction is not None:
            higher_seq_no = max([event.seq_no for event in transaction.transaction_event])
            if higher_seq_no > content["seq_no"]:
                #this event is old
                existing_transaction = transaction.get_dict_obj()
                content["transaction_info"] = {key: value for key, value in content["transaction_info"].items() if key not in existing_transaction or key == "transaction_id"}
 
        #introduce message in DB
        transaction_event = Transaction_Event(**content)
        self.session.merge(transaction_event)
    

    def setChargingProfile(self, cp_id, content):
        
        self.session.query(ChargingProfile).filter(ChargingProfile.id==content["charging_profile"]["id"]).delete()
        # for schedule in content["charging_profile"]["charging_schedule"]:
        #     self.session.query(ChargingSchedule).filter(ChargingSchedule.id==schedule["id"]).delete()

        content["charging_profile"].pop("charging_schedule")
        charging_profile = ChargingProfile(**content["charging_profile"])

        if content["evse_id"] is not None:
            if content["evse_id"] == 0:
                evses = self.session.query(EVSE).filter(EVSE.cp_id==cp_id).all()
            else:
                evses = [self.session.query(EVSE).get((content["evse_id"], cp_id))]
            
            charging_profile.evse = evses

        self.session.add(charging_profile)
    

    def delete_charging_profile(self, cp_id, content):
        #NOT WORKING
        pass
        #try:
        # if "charging_profile_id" in content and content["charging_profile_id"] is not None:
        #     self.session.query(ChargingProfile).filter(ChargingProfile.id==content["charging_profile_id"]).delete()
        # else:
        #     criteria = content["charging_profile_criteria"]
        #     query = self.session.query(ChargingProfile, evse_chargeProfiles)
            
        #     if "evse_id" in criteria and criteria["evse_id"] is None:
        #         query.filter(evse_chargeProfiles.evse_id==criteria["evse_id"]).filter(evse_chargeProfiles.cp_id==cp_id)
        #     if "charging_profile_purpose" in criteria and criteria["charging_profile_purpose"] is None:
        #         query.filter(ChargingProfile.charging_profile_purpose == criteria["charging_profile_purpose"])
        #     if "stack_level" in criteria and criteria["stack_level"] is None:
        #         query.filter(ChargingProfile.stack_level == criteria["stack_level"])
        #     query.delete()
        #except:
        #    logging.info("ERROR DELETING CHARGING PROFILES")


    
    def dates_overlap(self, valid_from1, valid_to1, valid_from2, valid_to2):

        valid_from1 = valid_from1 if valid_from1 is not None else datetime.now()
        valid_from2 = dateutil.parser.parse(valid_from2) if valid_from2 is not None else datetime.now()

        valid_to1 = valid_to1 if valid_to1 is not None else datetime.max
        valid_to2 = dateutil.parser.parse(valid_to2) if valid_to2 is not None else datetime.max

        if valid_from1 <= valid_to2 and valid_to1 >= valid_from2:
            return True
        
        return False
    

    def verify_charging_profile_conflicts(self, cp_id, content):

        charging_profile = ChargingProfile(**content["charging_profile"])

        conflict_ids = []
        
        if charging_profile.charging_profile_purpose == enums.ChargingProfilePurposeType.tx_profile:
            transaction_profiles = self.session.query(ChargingProfile).filter(ChargingProfile.transaction_id==charging_profile.transaction_id)

            for transaction_profile in transaction_profiles:
                if transaction_profile.id != charging_profile.id and \
                    transaction_profile.stack_level == charging_profile.stack_level:
                    conflict_ids.append(transaction_profile.id)

        else:
            #Other than txprofile
            if content["evse_id"] == 0:
                evses = self.session.query(EVSE).filter(EVSE.cp_id==cp_id).all()
            else:
                evses = [self.session.query(EVSE).get((content["evse_id"], cp_id))]

            for evse in evses:
                for evse_profile in evse.charging_profile:
                    if evse_profile.id != charging_profile.id and \
                        evse_profile.stack_level == charging_profile.stack_level and \
                        evse_profile.charging_profile_purpose == charging_profile.charging_profile_purpose and \
                        (
                            self.dates_overlap(evse_profile.valid_from, evse_profile.valid_to, charging_profile.valid_from, charging_profile.valid_to) 
                        ):

                        conflict_ids.append(evse_profile.id)
        
        return {"conflict_ids" : conflict_ids}
    



if __name__ == '__main__':
    # Main part
    loop = asyncio.new_event_loop()

    loop.create_task(DataBase().run())
    loop.run_forever()