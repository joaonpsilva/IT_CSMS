import asyncio

from rabbit_mq.rabbit_handler import Rabbit_Handler

import logging
import logging.config
from sqlalchemy import create_engine, update, select, delete, insert
from sqlalchemy.orm import sessionmaker
from CSMS.db.db_Tables import *
from ocpp.v201 import enums
import traceback
import argparse
import signal
import sys
from rabbit_mq.exceptions import ValidationError, OtherError
from pymysql.err import OperationalError


import dateutil.parser

logging.config.fileConfig("log.ini", disable_existing_loggers=False)
LOGGER = logging.getLogger("SQL_DB")


class DataBase:

    def __init__(self):

        self.table_mapping={
            "Modem":Modem,
            "Charge_Point":Charge_Point,
            "EVSE":EVSE,
            "Connector":Connector,
            "MeterValue":MeterValue,
            "SampledValue":SampledValue,
            "User": User,
            "IdToken":IdToken,
            "GroupIdToken":GroupIdToken,
            "IdTokenInfo":IdTokenInfo,
            "Transaction":Transaction,
            "Transaction_Event":Transaction_Event,
            "ChargingProfile":ChargingProfile,
            "EventData":EventData,
            "Reservation":Reservation
            }
    
    def shut_down(self, sig=None, frame=None):
        LOGGER.info("DB Shuting down")
        exit(0)

    async def on_db_request(self, request, retry_flag=False):
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
            
            return toReturn

        except OperationalError as e:
            #Handle Broken Pipe. Retry operation
            if retry_flag is True:
                raise e
            
            return await self.on_db_request(request, retry_flag=True)

        except Exception as e:
            self.session.rollback()
            raise e        


    async def run(self, db_address, rabbit, insert_hardCoded):

        try:
            #MySql engine
            self.engine = create_engine("mysql+pymysql://root:password123@" + db_address + ":3306/csms_db")

            #Create new sqlachemy session
            Session = sessionmaker(bind=self.engine)
            self.session = Session()

            #Create SQL tables
            await create_Tables(self.engine, self.session, insert_hardCoded)

            LOGGER.info("Connected to the database")

        except Exception:
            LOGGER.info("Could not connect to the Database")
            LOGGER.error(traceback.format_exc())
            self.shut_down()

        try:
            #Initialize broker that will handle Rabbit coms
            self.broker = Rabbit_Handler("SQL_DB", self.on_db_request)
            #Start listening to messages
            await self.broker.connect(rabbit, receive_responses=False)
        except:
            LOGGER.info("Could not connect to RabbitMq")
            self.shut_down()
        
        await asyncio.get_event_loop().create_future()
        

    def select(self, table, filters = {}, mode={}, cp_id=None, **kwargs):
        statement = select(self.table_mapping[table]).filter_by(**filters)
        return [obj.get_dict_obj(mode, cp_id=cp_id) for obj in self.session.scalars(statement).all()]
    
    #TODO change the return
    def create(self, table, values={}, **kwargs):
        obj = self.table_mapping[table](**values)
        self.session.add(obj)
        return obj
    
    def remove(self, table, filters ={}, **kwargs):
        return self.session.query(self.table_mapping[table]).filter_by(**filters).delete()

    def update(self, table, filters={},values={}, **kwargs):
        return self.session.query(self.table_mapping[table]).filter_by(**filters).update(values)


    def register(self, cp_id=None, **content):
        user = self.session.query(User).filter_by(email=content["email"]).first()
        
        if user:
            raise ValidationError("User already exists")
        
        if content["_id_token"]:
            id_token = self.session.query(IdToken).filter_by(id_token=content["_id_token"]).first()
            if not id_token:
                raise ValidationError("Invalid Id Token")

        user = User(**content)
        self.session.add(user)
        
        return user.get_dict_obj()


    def login(self, email, password, **kwargs):
        user = self.session.query(User).filter_by(email=email).first()

        if not user or not user.verify_password(password):
            raise OtherError("Invalid User or Password")
        
        id_token = None
        if user.id_token is not None:
            id_token = user.id_token.get_dict_obj()

        response = {"id" : user.id, "permission_level" : user.permission_level, "id_token" : id_token}

        return response


    def verify_password(self, CP_ID, password, **kwargs):
        charge_point = self.session.query(Charge_Point).get(CP_ID)

        try:
            return {"approved" : charge_point.verify_password(password)}
        
        except:
            return {"approved" : False}
    

    def update_User_password(self, user_id, password, **kwargs):
        user = self.session.query(User).get(user_id)
        user.password = password
        return user.get_dict_obj()
    
    def update_CP_password(self, cp_id, password, **kwargs):
        charge_point = self.session.query(Charge_Point).get(cp_id)
        charge_point.password = password
        return charge_point.get_dict_obj()


    def create_new_Group_IdToken(self, type=None, id_token=None, **kwargs):
        id_token = GroupIdToken(type=type, id_token=id_token)
        self.session.add(id_token)
        return id_token.get_dict_obj()
    

    def create_new_IdToken(self, cp_id, type=None, id_token=None, **kwargs):
        
        id_token = IdToken(type=type, id_token=id_token)
        id_token_info = IdTokenInfo(**kwargs)
        
        evses = self.session.query(EVSE).all()
        id_token_info.evse = evses
        
        id_token.id_token_info = id_token_info

        self.session.add(id_token)
        return id_token.get_dict_obj()
    

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


    def collect_important_metervalues(self, transaction_event, transaction_info):

        transaction_info["cable_max_current"] = transaction_event.cable_max_current

        #check meter values
        if len(transaction_event.meter_value) > 0:
            for mv in transaction_event.meter_value:
                for sv in mv.sampled_value:
                    if sv.location == enums.LocationType.outlet:
                        if sv.measurand == enums.MeasurandType.power_active_export:
                            transaction_info["power_export"] = sv.value

                        elif sv.measurand == enums.MeasurandType.power_active_import:
                            transaction_info["power_import"] = sv.value

                        elif sv.measurand == enums.MeasurandType.soc:
                            transaction_info["soc"] = sv.value

                        elif sv.measurand == enums.MeasurandType.energy_active_export_register:
                            if sv.context == enums.ReadingContextType.transaction_begin or transaction_event.seq_no==0:
                                transaction_info["initial_export"] = sv.value
                            transaction_info["final_export"] = sv.value
                            
                        elif sv.measurand == enums.MeasurandType.energy_active_import_register:
                            if sv.context == enums.ReadingContextType.transaction_begin or transaction_event.seq_no==0:
                                transaction_info["initial_import"] = sv.value
                            transaction_info["final_import"] = sv.value
        
        return transaction_info


    def TransactionEvent(self, cp_id, id_token=None, evse=None, **content):
        #introduce cp_id in message, store evse_id and connector_id in better format
        if evse:
            #evse["evse_id"] = evse.pop("id")
            #content = {**content, **evse}  
            content["connector_id"] = evse["connector_id"]  if "connector_id" in evse else None
            content["transaction_info"]["evse_id"] = evse["id"]
        content["transaction_info"]["cp_id"] = cp_id

        
        #separate transation object and remove Nones
        transaction_info = content.pop("transaction_info")

        transaction_info = {k: v for k, v in transaction_info.items() if v is not None}

        #Instantiate event obj
        transaction_event = Transaction_Event(**content)

        transaction_info = self.collect_important_metervalues(transaction_event, transaction_info)

        #active var in transaction
        if transaction_event.event_type == enums.TransactionEventType.ended:
            transaction_info["active"] = False

        #check if there is a more recent event. (Dont update transaction)
        transaction = self.session.query(Transaction).get(transaction_info["transaction_id"])
        if transaction is not None:
            higher_seq_no = max([event.seq_no for event in transaction.transaction_event])
            if higher_seq_no > transaction_event.seq_no:
                #this event is old
                existing_transaction = transaction.get_dict_obj()
                transaction_info = {key: value for key, value in transaction_info.items() if existing_transaction[key] is None}
                
            for key, value in transaction_info.items():
                setattr(transaction, key, value)
        else:
            transaction = Transaction(**transaction_info)
        
        #connect idtoken with transaction and event
        if id_token:
            id_token = self.session.query(IdToken).get(id_token["id_token"])
            if id_token is not None:
                if id_token.id_token not in [token.id_token for token in transaction.id_token]:
                    transaction.id_token.append(id_token)
                transaction_event.id_token = id_token

        #connect transaction with event
        transaction_event.transaction_info = transaction
        
        self.session.merge(transaction_event)
    

    def new_Reservation(self, id_token, group_id_token=None, **reservation):
        
        reservation = Reservation(**reservation)

        id_token = self.session.query(IdToken).get(id_token["id_token"])
        if id_token is not None:
            reservation.id_token = id_token
        
        group_id_token = self.session.query(GroupIdToken).get(group_id_token["id_token"]) if group_id_token else None
        if group_id_token is not None:
            reservation.group_id_token = group_id_token
        
        self.session.add(reservation)
    

    def get_Open_Transactions_byIdToken(self, id_token, **kwargs):
        """method for a specific api endpoint"""
        transactions = self.session.query(Transaction).join(Transaction.id_token).filter(
            IdToken.id_token == id_token,
            Transaction.active == True
        ).all()

        return [t.get_dict_obj() for t in transactions]
    
    
    def get_Transactions_byDate(self, id_token, date, **kwargs):
        """method for a specific api endpoint"""
        transactions = self.session.query(Transaction).join(Transaction.id_token).join(Transaction.transaction_event).filter(
            IdToken.id_token == id_token,
            Transaction_Event.timestamp >= dateutil.parser.parse(date)
        ).all()

        return [t.get_dict_obj() for t in transactions]


    def get_charging_profiles_criteria(self, cp_id=None, evse_id=None, charging_profile_purpose=None, stack_level=None, id=None):

        profiles = self.session.query(ChargingProfile)
        filters = []
        
        if cp_id is not None:
            profiles = profiles.join(ChargingProfile.evse)
            filters.append(EVSE.cp_id == cp_id)

            if evse_id == 0 or evse_id is None:
                evse_id = None    
            else:
                filters.append(EVSE.evse_id == evse_id)
        
        if charging_profile_purpose:
            filters.append(ChargingProfile.charging_profile_purpose == charging_profile_purpose)
        if stack_level:
            filters.append(ChargingProfile.stack_level == stack_level)
        if id:
            filters.append(ChargingProfile.id == id)

        return profiles.filter(*filters)


    def get_charging_profiles(self, **kwargs):
        return [obj.get_dict_obj() for obj in self.get_charging_profiles_criteria(**kwargs).all()]
    

    def clearChargingProfile(self, cp_id, charging_profile_id, charging_profile_criteria, **kwargs):
        self.get_charging_profiles_criteria(cp_id, **charging_profile_criteria, id=charging_profile_id).delete()
 

    def create_Charging_profile(self, cp_id,  evse_id, charging_profile, **kwargs):
        
        if "id" in charging_profile and charging_profile["id"] is not None:
            self.session.query(ChargingProfile).filter(ChargingProfile.id==charging_profile["id"]).delete()
        
        for schedule in charging_profile["charging_schedule"]:
            if "id" in schedule and schedule["id"] is not None:
                self.session.query(ChargingSchedule).filter(ChargingSchedule.id==schedule["id"]).delete()

        
        charging_profile = ChargingProfile(**charging_profile)

        if evse_id == 0:
            evses = self.session.query(EVSE).filter(EVSE.cp_id==cp_id).all()
        else:
            evses = [self.session.query(EVSE).get((evse_id, cp_id))]
        charging_profile.evse = evses

        self.session.add(charging_profile)
        #return charging_profile.get_dict_obj(mode={"relationships":{"charging_schedule":{}}})
    
    
if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("-rb", type=str, default = "amqp://guest:guest@localhost/", help="RabbitMq")
    parser.add_argument("-db", type=str, default = "localhost", help="database address")

    parser.add_argument("-i", action="store_true", help="insert hardcoded objects")

    args = parser.parse_args()

    # Main part
    loop = asyncio.new_event_loop()

    #init db
    db = DataBase()

    #shut down handler
    signal.signal(signal.SIGINT, db.shut_down)
    
    asyncio.run(db.run(args.db, args.rb, args.i))