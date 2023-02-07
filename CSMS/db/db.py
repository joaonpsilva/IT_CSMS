import asyncio

import sys
from os import path
sys.path.append( path.dirname(path.dirname( path.dirname( path.abspath(__file__) ) ) ))
from rabbit_handler import Rabbit_Handler

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
import signal

import dateutil.parser


LOGGER = logging.getLogger("SQL_DB")
LOGGER.setLevel(logging.DEBUG)

# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

LOGGER.addHandler(ch)


class DataBase:

    def __init__(self):

        #MySql engine
        self.engine = create_engine("mysql+pymysql://root:password123@localhost:3306/csms_db")
        LOGGER.info("Connected to the database")

        #Create new sqlachemy session
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        #Create SQL tables
        create_Tables(self.engine)

        #Insert some CPs (testing)
        insert_Hard_Coded(self)


        self.table_mapping={
            "Modem":Modem,
            "Charge_Point":Charge_Point,
            "EVSE":EVSE,
            "Connector":Connector,
            "MeterValue":MeterValue,
            "SignedMeterValue":SignedMeterValue,
            "SampledValue":SampledValue,
            "User": User,
            "IdToken":IdToken,
            "GroupIdToken":GroupIdToken,
            "IdTokenInfo":IdTokenInfo,
            "Transaction":Transaction,
            "Transaction_Event":Transaction_Event,
            "ChargingProfile":ChargingProfile,
            "EventData":EventData,
            }
    
    def shut_down(self, sig, frame):
        LOGGER.info("DB Shuting down")
        sys.exit(0)


    async def on_db_request(self, request):
        """
        Function that will handle incoming requests from the api or ocpp Server
        """
        try:
            #get method depending on the message
            method = getattr(self, request.method)
        except AttributeError:
            return

        try:
            #call method
            toReturn = method(cp_id=request.cp_id, **request.content)
            #commit possible changes
            self.session.commit()
            
            return {"status":"OK", "content":toReturn}
        
        except ValueError as e:
            self.session.rollback()
            return {"status" : "VAL_ERROR" , "content": e.args[0]}
        
        except AssertionError as e:
            self.session.rollback()
            return {"status" : "OTHER_ERROR" , "content": e.args[0]}

        except Exception as e:
            self.session.rollback()
            LOGGER.error(traceback.format_exc())
            return {"status":"ERROR"}


    async def run(self, rabbit):

        #Initialize broker that will handle Rabbit coms
        self.broker = Rabbit_Handler("SQL_DB", self.on_db_request)
        #Start listening to messages
        await self.broker.connect(rabbit, receive_responses=False)
    

    def select(self, table, filters = {}, mode={}, **kwargs):
        statement = select(self.table_mapping[table]).filter_by(**filters)
        return [obj.get_dict_obj(mode) for obj in self.session.scalars(statement).all()]
    
    def create(self, table, values={}, **kwargs):
        obj = self.table_mapping[table](**values)
        self.session.add(obj)
    
    def remove(self, table, filters ={}, **kwargs):
        statement = delete(self.table_mapping[table]).filter_by(**filters)
        self.session.execute(statement)

    def update(self, table, filters={},values={}, **kwargs):
        statement = update(self.table_mapping[table]).filter_by(**filters).values(**values)
        self.session.execute(statement)


    def register(self, cp_id=None, **content):
        
        user = self.session.query(User).filter_by(email=content["email"]).first()
        
        if user:
            raise ValueError("User already exists")

        user = User(**content)
        self.session.add(user)


    def login(self, email, password, **kwargs):
        user = self.session.query(User).filter_by(email=email).first()

        if not user or not user.verify_password(password):
            raise AssertionError("Invalid User or Password")

        response = {"u_id" : user.id}
        if user.id_token:
            response["card_id_token"] = user.id_token.id_token

        return response



    def verify_password(self, CP_ID, password, **kwargs):
        charge_point = self.session.query(Charge_Point).get(CP_ID)

        try:
            return {"approved" : charge_point.verify_password(password)}
        
        except:
            return {"approved" : False}


    def BootNotification(self, cp_id, **content):

        content["charging_station"]["cp_id"] = cp_id
        bootNotification = BootNotification(**content)
        
        self.session.merge(bootNotification)

    def StatusNotification(self, cp_id, connector_id,evse_id, **content):

        content["connector"] = {"cp_id": cp_id, "evse_id":evse_id, "connector_id":connector_id, "connector_status":content["connector_status"]}

        statusNotification = StatusNotification(**content)
        self.session.merge(statusNotification)
        

    def MeterValues(self, cp_id, **content): 
        
        evse_id = content["evse_id"]

        for meter_value_dict in content["meter_value"]:

            meter_value_dict["cp_id"] = cp_id
            meter_value_dict["evse_id"] = evse_id

            meter_value = MeterValue(**meter_value_dict)
            self.session.add(meter_value)

    
    def get_IdToken_Info(self, cp_id, id_token, **kwargs):

        #get Idtoken fromdb
        idToken = self.session.query(IdToken).get(id_token["id_token"])
        if idToken is None:
            return {"id_token" : None, "id_token_info" : None}
        
        #transform do dict
        idToken_dict = idToken.get_dict_obj()

        #get idtokeninfo from idtoken
        idTokenInfo = idToken.id_token_info
        #transform to dict
        idTokenInfo_dict = idTokenInfo.get_dict_obj(mode={"relationships":{"group_id_token":{}}})
        #append allowed evseids
        idTokenInfo_dict["evse_id"] = idTokenInfo.get_allowed_evse_for_cp(cp_id) 
        
        return {"id_token" : idToken_dict, "id_token_info" : idTokenInfo_dict}
    


    def verify_received_all_transaction(self, cp_id, transaction_id, **kwargs):
        
        response = {"status" : "OK"}
        try:
            
            transaction = self.session.query(Transaction).get(transaction_id)
            assert(transaction is not None)

            transaction_events = sorted(transaction.transaction_event, key=lambda t : t.seq_no)
            assert(transaction_events[0].event_type == enums.TransactionEventType.started)

            if transaction_events[-1].event_type != enums.TransactionEventType.ended or\
                transaction_events[-1].seq_no - transaction_events[0].seq_no > len(transaction_events)-1:
                response["status"] = "MISSING_MESSAGES"
        except:
            response["status"] = "ERROR"

        return response



    def TransactionEvent(self, cp_id, **content):
        
        #If message contains idtoken
        if "id_token" in content:
            #if for some reason, this idtoken is not good, dont use it to store in db

            q = self.session.query(IdToken).filter(IdToken.id_token==content["id_token"]["id_token"])
            exists = self.session.query(q.exists()).scalar()
            if not exists:
                content.pop("id_token")

        #introduce cp_id in message, store evse_id and connector_id in better format
        LOGGER.info(content)
        if "evse" in content and content["evse"]:
            content["evse"]["evse_id"] = content["evse"].pop("id")
            evse = content.pop("evse")
            content = {**content, **evse}
        LOGGER.info(content)
        
        content["transaction_info"]["cp_id"] = cp_id


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
    

    def get_charging_profiles(self, cp_id, evse_id, charging_profile_purpose, stack_level):

        if evse_id == 0:
            evse_ids = [evse.evse_id for evse in self.session.query(EVSE).filter(EVSE.cp_id==cp_id).all()]
        else:
            evse_ids = [evse_id]

        result = []
        for evse_id in evse_ids:

            profiles = self.session.query(ChargingProfile).join(ChargingProfile.evse).filter(
                EVSE.cp_id == cp_id,
                EVSE.evse_id == evse_id,
                ChargingProfile.charging_profile_purpose == charging_profile_purpose,
                ChargingProfile.stack_level == stack_level
            ).all()

            result += [obj.get_dict_obj() for obj in profiles]

        return result



    def create_Charging_profile(self, cp_id,  evse_id, charging_profile, **kwargs):
        
        if "id" in charging_profile and charging_profile["id"] is not None:
            self.session.query(ChargingProfile).filter(ChargingProfile.id==charging_profile["id"]).delete()
        
        charging_profile = ChargingProfile(**charging_profile)

        if evse_id == 0:
            evses = self.session.query(EVSE).filter(EVSE.cp_id==cp_id).all()
        else:
            evses = [self.session.query(EVSE).get((evse_id, cp_id))]
        charging_profile.evse = evses

        self.session.add(charging_profile)
        self.session.commit()
        self.session.refresh(charging_profile)
        
        return charging_profile.id



    def verify_charging_profile_conflicts(self, cp_id, **content):

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

    #init db
    db = DataBase()

    #shut down handler
    signal.signal(signal.SIGINT, db.shut_down)

    loop.create_task(db.run(args.rb))
    loop.run_forever()