import asyncio
from db_Rabbit_Handler import DB_Rabbit_Handler
import logging
from sqlalchemy import create_engine, update, select, delete, insert
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import exists, text
from db_Tables import *
from sqlalchemy.orm.util import identity_key
from ocpp.v201 import enums
from datetime import datetime
import traceback
import argparse

import dateutil.parser

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
        create_Tables(self.engine)

        #Insert some CPs (testing)
        insert_Hard_Coded(self)


        #map incoming messages to methods
        self.method_mapping={
            "BootNotification" : self.BootNotification,
            "StatusNotification" : self.StatusNotification,
            "MeterValues" : self.MeterValues,
            "get_IdToken_Info" : self.get_IdToken_Info,
            "TransactionEvent" : self.TransactionEvent,
            "VERIFY_PASSWORD" : self.verify_password,
            "VERIFY_RECEIVED_ALL_TRANSACTION" : self.verify_received_all_transaction,
            "VERIFY_CHARGING_PROFILE_CONFLICTS" : self.verify_charging_profile_conflicts,
            "SetChargingProfile" : self.setChargingProfile,
            "SELECT" : self.select,
            "CREATE" : self.create,
            "REMOVE" : self.remove,
            "UPDATE" : self.update
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


    async def on_db_request(self, request):
        """
        Function that will handle incoming requests from the api or ocpp Server
        """
        if request.method in self.method_mapping:
            try:
                #call method depending on the message
                toReturn = self.method_mapping[request.method](**request.__dict__)
                #commit possible changes
                self.session.commit()

                return {"status":"OK", "content":toReturn}
            except Exception as e:
                self.session.rollback()
                logging.error(traceback.format_exc())
                return {"status":"ERROR"}


    async def run(self, rabbit):

        #Initialize broker that will handle Rabbit coms
        self.broker = DB_Rabbit_Handler("db1", self.on_db_request)
        #Start listening to messages
        await self.broker.connect(rabbit)

    def get_class_attributes(self, c):
        return [attr for attr in dir(c) if not callable(getattr(c, attr)) and not attr.startswith("_")]
    

    def select(self, content, **kwargs):
        if "filters" not in content:
            content["filters"] = {}
        statement = select(self.table_mapping[content["table"]]).filter_by(**content["filters"])
        return [obj.get_dict_obj() for obj in self.session.scalars(statement).all()]
    
    def create(self, content, **kwargs):
        statement = insert(self.table_mapping[content["table"]]).values(**content["values"])
        self.session.execute(statement)
    
    def remove(self, content, **kwargs):
        if "filters" not in content:
            content["filters"] = {}
        statement = delete(self.table_mapping[content["table"]]).filter_by(**content["filters"])
        self.session.execute(statement)

    def update(self, content, **kwargs):
        if "filters" not in content:
            content["filters"] = {}
        statement = update(self.table_mapping[content["table"]]).filter_by(**content["filters"]).values(**content["values"])
        self.session.execute(statement)



    def verify_password(self, cp_id, content, **kwargs):
        charge_point = self.session.query(Charge_Point).get(cp_id)

        result = False
        if charge_point is not None:
            result = charge_point.verify_password(content["password"])

        return {"approved" : result}



    def BootNotification(self, cp_id, content, **kwargs):

        content["charging_station"]["cp_id"] = cp_id
        bootNotification = BootNotification(**content)
        
        self.session.merge(bootNotification)

    def StatusNotification(self, cp_id, content, **kwargs):

        connector_id = content.pop("connector_id")
        evse_id = content.pop("evse_id")
        content["connector"] = {"cp_id": cp_id, "evse_id":evse_id, "connector_id":connector_id}

        statusNotification = StatusNotification(**content)
        self.session.merge(statusNotification)
        

    def MeterValues(self, cp_id, content, **kwargs): 
        
        evse_id = content["evse_id"]

        for meter_value_dict in content["meter_value"]:

            meter_value_dict["cp_id"] = cp_id
            meter_value_dict["evse_id"] = evse_id

            meter_value = MeterValue(**meter_value_dict)
            self.session.add(meter_value)

    
    def get_IdToken_Info(self, content, cp_id, **kwargs):

        #get Idtoken fromdb
        idToken = self.session.query(IdToken).get(content['id_token']["id_token"])
        if idToken is None:
            return {"id_token" : None, "id_token_info" : None}
        
        #transform do dict
        idToken_dict = idToken.get_dict_obj()

        #get idtokeninfo from idtoken
        idTokenInfo = idToken.id_token_info
        #load groupid from info
        idTokenInfo.group_id_token
        #transform to dict
        idTokenInfo_dict = idTokenInfo.get_dict_obj()
        #append allowed evseids
        idTokenInfo_dict["evse_id"] = idTokenInfo.get_allowed_evse_for_cp(cp_id) 
        
        return {"id_token" : idToken_dict, "id_token_info" : idTokenInfo_dict}
    


    def verify_received_all_transaction(self, cp_id, content, **kwargs):
        
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



    def TransactionEvent(self, cp_id, content, **kwargs):
        
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
    

    def setChargingProfile(self, cp_id, content, **kwargs):
        
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

    
    def dates_overlap(self, valid_from1, valid_to1, valid_from2, valid_to2):

        valid_from1 = valid_from1 if valid_from1 is not None else datetime.now()
        valid_from2 = dateutil.parser.parse(valid_from2) if valid_from2 is not None else datetime.now()

        valid_to1 = valid_to1 if valid_to1 is not None else datetime.max
        valid_to2 = dateutil.parser.parse(valid_to2) if valid_to2 is not None else datetime.max

        if valid_from1 <= valid_to2 and valid_to1 >= valid_from2:
            return True
        
        return False
    

    def verify_charging_profile_conflicts(self, cp_id, content, **kwargs):

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

    parser = argparse.ArgumentParser()
    parser.add_argument("-rb", type=str, default = "amqp://guest:guest@localhost/", help="RabbitMq")
    args = parser.parse_args()

    # Main part
    loop = asyncio.new_event_loop()

    loop.create_task(DataBase().run(args.rb))
    loop.run_forever()