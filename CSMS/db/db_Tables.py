from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Enum, ForeignKeyConstraint, Float, Table, Boolean, JSON
from sqlalchemy.orm import declarative_base, relationship, backref
from ocpp.v201 import enums
from passlib.context import CryptContext
from sqlalchemy.inspection import inspect

import sys
from os import path
sys.path.append( path.dirname(path.dirname( path.dirname( path.abspath(__file__) ) ) ))
from database_Base import *
from sqlalchemy.sql import true



PASSLIB_CONTEXT = CryptContext(
    # in a new application with no previous schemes, start with pbkdf2 SHA512
    schemes=["pbkdf2_sha512"],
    deprecated="auto",
)

def generate_hash(password):
    """Generate a secure password hash from a new password"""
    return PASSLIB_CONTEXT.hash(password.encode("utf8"))


class Modem(CustomBase):
    __tablename__ = "Modem"
    iccid = Column(String(20), primary_key=True)
    imsi = Column(String(20), primary_key=True)

    _cp_id = Column(String(20), ForeignKey("Charge_Point.cp_id"))

    def __init__(self, iccid="NULL", imsi="NULL", **kwargs):
        kwargs["iccid"] = iccid
        kwargs["imsi"] = imsi

        super().__init__(**kwargs)


class Charge_Point(CustomBase):
    __tablename__ = "Charge_Point"
    cp_id = Column(String(20), primary_key=True)
    _password_hash = Column(String(256)) #https://stackoverflow.com/questions/56738384/sqlalchemy-call-function-and-save-returned-value-in-table-always
    
    model = Column(String(20))
    vendor_name = Column(String(50))
    serial_number = Column(String(25))
    firmware_version = Column(String(50))

    city = Column(String(50))
    latitude = Column(String(50))
    longitude = Column(String(50))
    country = Column(String(50))
    ocpp_version = Column(String(50))
    is_online = Column(Boolean)


    modem = relationship("Modem", backref="charge_point", uselist=False)

    def __init__(self, password=None, **kwargs):
        
        if password:
            password_hash = generate_hash(password) #Encript password (Hash)
            kwargs["_password_hash"] = password_hash
        
        super().__init__(**kwargs)
    
    @property
    def password(self):
        raise AttributeError("User.password is write-only")
    
    @password.setter
    def password(self, password):
        self._password_hash = generate_hash(password)
    
    def verify_password(self, password):
        return PASSLIB_CONTEXT.verify(password, self._password_hash)


class BootNotification(CustomBase):
    __tablename__ = "BootNotification"

    message_id = Column(Integer, primary_key=True)
    reason = Column(Enum(enums.BootReasonType))
    timestamp = Column(DateTime)
    cp_id = Column(String(20), ForeignKey("Charge_Point.cp_id"))

    charging_station = relationship("Charge_Point", backref="boot_nofications", uselist=False)



class EVSE(CustomBase):
    __tablename__ = "EVSE"
    evse_id = Column(Integer, primary_key=True)   #This id is only unique inside each CP

    cp_id = Column(String(20), ForeignKey("Charge_Point.cp_id"), primary_key=True)
    charge_point = relationship("Charge_Point", backref="evse")

    def __init__(self, id = None, **kwargs):
        if id:
            kwargs["evse_id"] = id
        super().__init__(**kwargs)


class Connector(CustomBase):
    __tablename__ = "Connector"

    connector_id = Column(Integer, primary_key=True) #This id is only unique inside each EVSE
    connector_type = Column(Enum(enums.ConnectorType))
    connector_status = Column(Enum(enums.ConnectorStatusType))

    cp_id = Column(String(20), primary_key=True)
    evse_id = Column(Integer, primary_key=True)
    __table_args__ = (ForeignKeyConstraint(["cp_id", "evse_id"],
                                            [ "EVSE.cp_id", "EVSE.evse_id"]),{})

    evse = relationship("EVSE", backref="connector")


class StatusNotification(CustomBase):
    __tablename__ = "StatusNotification"

    message_id = Column(Integer, primary_key=True)
    connector_status = Column(Enum(enums.ConnectorStatusType))
    timestamp = Column(DateTime)
    
    cp_id = Column(String(20))
    evse_id = Column(Integer)
    connector_id = Column(Integer)
    __table_args__ = (ForeignKeyConstraint(["cp_id", "evse_id", "connector_id"],
                                            [ "Connector.cp_id", "Connector.evse_id", "Connector.connector_id"]),{})

    connector = relationship("Connector", backref="status_nofications", uselist=False)

####################################################################################

evse_idTokens = Table(
    'evse_idTokens',
    Base.metadata,
    Column('cp_id', String(20)),
    Column('evse_id', Integer),
    Column('id_token', String(36), ForeignKey('IdTokenInfo._id_token')),
    ForeignKeyConstraint(("cp_id", "evse_id"),
                        ("EVSE.cp_id", "EVSE.evse_id"))
)

class User(CustomBase):
    __tablename__ = "User"
    id = Column(Integer, primary_key = True)
    cust_id = Column(Integer)
    full_name = Column(String(256))
    email = Column(String(256), nullable = False, unique=True, index=True)
    status = Column(String(256))
    _password_hash = Column(String(256))

    id_token = relationship("IdToken", backref=backref("user", uselist=False), uselist=False)

    def __init__(self, password=None, **kwargs):
        
        if password:
            password_hash = generate_hash(password) #Encript password (Hash)
            kwargs["_password_hash"] = password_hash
        
        super().__init__(**kwargs)
    
    @property
    def password(self):
        raise AttributeError("User.password is write-only")
    
    @password.setter
    def password(self, password):
        self._password_hash = generate_hash(password)
    
    
    def verify_password(self, password):
        return PASSLIB_CONTEXT.verify(password, self._password_hash)



class IdToken(CustomBase):
    __tablename__ = "IdToken"
    id_token = Column(String(36), primary_key=True)
    type = Column(Enum(enums.IdTokenType))

    _user_id = Column(Integer, ForeignKey("User.id"))

    def __init__(self, additional_info=None, **kwargs):
        super().__init__(**kwargs)


class GroupIdToken(CustomBase):
    __tablename__ = "GroupIdToken"
    id_token = Column(String(36), primary_key=True)
    type = Column(Enum(enums.IdTokenType))

    def __init__(self, additional_info=None, **kwargs):
        super().__init__(**kwargs)


class IdTokenInfo(CustomBase):
    __tablename__ = "IdTokenInfo"

    valid = Column(Boolean)

    _id_token = Column(String(36), ForeignKey("IdToken.id_token"), primary_key=True)
    id_token = relationship("IdToken", backref=backref("id_token_info", uselist=False), uselist=False)

    cache_expiry_date_time = Column(DateTime)
    charging_priority = Column(Integer)
    language1 = Column(String(8))
    language2 = Column(String(8))
    evse = relationship('EVSE', secondary=evse_idTokens, backref='id_token_info')
    
    _group_id_token = Column(String(36), ForeignKey("GroupIdToken.id_token"))
    group_id_token = relationship("GroupIdToken", backref="id_token_info", uselist=False)

    
    def get_allowed_evse_for_cp(self, cp_id):
            
        #get evse in which can charge in this cp
        return [evse.evse_id for evse in self.evse if evse.cp_id == cp_id]            
        



############################################################################3

class MeterValue(CustomBase):
    __tablename__ = "MeterValue"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime)

    cp_id = Column(String(20))
    evse_id = Column(Integer)
    evse = relationship("EVSE", backref="meter_value", uselist=False)

    seq_no = Column(Integer)
    transaction_id = Column(String(36))

    __table_args__ = (ForeignKeyConstraint(["cp_id", "evse_id"],
                                    ["EVSE.cp_id", "EVSE.evse_id"]),
                    ForeignKeyConstraint(["transaction_id", "seq_no"],
                                    ["Transaction_Event.transaction_id", "Transaction_Event.seq_no"]),{})


class SampledValue(CustomBase):
    __tablename__ = "SampledValue"
    id = Column(Integer, primary_key=True)

    value = Column(Float, nullable=False)
    context = Column(Enum(enums.ReadingContextType))
    measurand = Column(Enum(enums.MeasurandType))
    phase = Column(Enum(enums.PhaseType))
    location = Column(Enum(enums.LocationType))
    unit = Column(String(20))
    multiplier = Column(Integer)

    _meter_value_id = Column(Integer, ForeignKey("MeterValue.id"))
    meter_value = relationship("MeterValue", backref="sampled_value", uselist=False)

    signed_meter_value = Column(JSON)

    def __init__(self, unit_of_measure=None, measurand=enums.MeasurandType.energy_active_export_register, location=enums.LocationType.outlet, **kwargs):
        if unit_of_measure:
            for key, value in unit_of_measure.items():
                kwargs[key] = value
        
        kwargs["measurand"] = measurand
        kwargs["location"] = location

        super().__init__(**kwargs)
    


idToken_Transactions = Table(
    'idToken_Transactions',
    Base.metadata,
    Column('id_token', String(36), ForeignKey("IdToken.id_token")),
    Column('transaction_id', String(36), ForeignKey("Transaction.transaction_id"))
)

class Transaction(CustomBase):
    __tablename__ = "Transaction"
    transaction_id = Column(String(36), primary_key=True)
    charging_state = Column(Enum(enums.ChargingStateType))
    time_spent_charging = Column(Integer)
    stopped_reason = Column(Enum(enums.ReasonType))
    remote_start_id = Column(Integer, unique=True)

    active = Column(Boolean, server_default=true())

    initial_export = Column(Float)
    final_export = Column(Float)
    initial_import = Column(Float)
    final_import = Column(Float)
    soc = Column(Float)
    power_export = Column(Float)
    power_import = Column(Float)

    cp_id = Column(String(20), ForeignKey("Charge_Point.cp_id"))
    evse_id = Column(Integer)
    __table_args__ = (ForeignKeyConstraint(["cp_id", "evse_id"],
                                [ "EVSE.cp_id", "EVSE.evse_id"]),{})
    charge_point = relationship("Charge_Point", backref="transaction", uselist=False)
    evse = relationship("EVSE", backref=backref("transaction", overlaps="charge_point,transaction"), uselist=False, overlaps="charge_point,transaction")
    #evse = relationship("EVSE", backref="transaction", uselist=False)

    id_token = relationship("IdToken", secondary=idToken_Transactions, backref="transaction")
    

class Transaction_Event(CustomBase):
    __tablename__ = "Transaction_Event"

    event_type = Column(Enum(enums.TransactionEventType))
    timestamp = Column(DateTime)
    trigger_reason = Column(Enum(enums.TriggerReasonType))
    offline = Column(Boolean)
    number_of_phases_used = Column(Integer)
    cable_max_current = Column(Integer)
    reservation_id = Column(Integer)
    seq_no = Column(Integer, primary_key = True)

    #Id_Token
    _id_token = Column(String(36), ForeignKey("IdToken.id_token"))
    id_token = relationship("IdToken", backref="transaction_event", uselist=False)

    #EVSE, Connector
    #No foreign key? correct?
    connector_id = Column(Integer)
    #evse_id = Column(Integer)

    """
    __table_args__ = (ForeignKeyConstraint(["cp_id", "evse_id"],
                                [ "EVSE.cp_id", "EVSE.evse_id"]),
                ForeignKeyConstraint(["cp_id", "evse_id", "connector_id"],
                                [ "Connector.cp_id", "Connector.evse_id", "Connector.connector_id"]),{})

    evse = relationship("EVSE", backref=backref("transaction", overlaps="Charge_Point,transaction"), uselist=False, overlaps="Charge_Point,transaction")
    connector = relationship("Connector", backref=backref("transaction", overlaps="Charge_Point,evse,transaction"), uselist=False, overlaps="Charge_Point,evse,transaction")
    """

    #Transaction
    transaction_id = Column(String(36), ForeignKey("Transaction.transaction_id"), primary_key = True)
    transaction_info = relationship("Transaction", backref="transaction_event",uselist=False)

    #Meter value
    meter_value = relationship("MeterValue", backref=backref("transaction_event", uselist=False))



##############################################################################3

evse_chargeProfiles = Table(
    'evse_chargeProfiles',
    Base.metadata,
    Column('cp_id', String(20)),
    Column('evse_id', Integer),
    Column('id', Integer, ForeignKey('ChargingProfile.id', ondelete="CASCADE")),
    ForeignKeyConstraint(("cp_id", "evse_id"),
                        ("EVSE.cp_id", "EVSE.evse_id"))
)


class ChargingProfile(CustomBase):
    __tablename__ = "ChargingProfile"

    id = Column(Integer, primary_key = True)
    stack_level = Column(Integer)
    charging_profile_purpose = Column(Enum(enums.ChargingProfilePurposeType))
    charging_profile_kind = Column(Enum(enums.ChargingProfileKindType))
    recurrency_kind = Column(Enum(enums.RecurrencyKindType))
    valid_from = Column(DateTime)
    valid_to = Column(DateTime)

    transaction_id = Column(String(36), ForeignKey('Transaction.transaction_id'))
    transaction = relationship("Transaction", backref="charging_profile",uselist=False)

    evse = relationship('EVSE', secondary=evse_chargeProfiles, backref='charging_profile')
    charging_schedule = relationship("ChargingSchedule", backref="charging_profile")


class ChargingSchedule(CustomBase):
    __tablename__ = "ChargingSchedule"

    id = Column(Integer, primary_key = True)
    start_schedule = Column(DateTime)
    duration = Column(Integer)
    charging_rate_unit = Column(Enum(enums.ChargingRateUnitType))
    min_charging_rate = Column(Float)

    _charging_profile = Column(Integer, ForeignKey("ChargingProfile.id"))
    sales_tariff = Column(JSON)




class EventData(CustomBase):
    __tablename__ = "EventData"
    event_id = Column(Integer, primary_key = True)
    timestamp = Column(DateTime)
    trigger = Column(Enum(enums.EventTriggerType))
    cause = Column(Integer, ForeignKey("EventData.event_id"))
    actual_value = Column(String(2500)) 
    tech_code = Column(String(50))
    tech_info = Column(String(500))
    cleared = Column(Boolean)
    transaction_id = Column(String(36), ForeignKey("Transaction.transaction_id"))
    variable_monitoring_id = Column(Integer)
    event_notification_type = Column(Enum(enums.EventNotificationType))

    component = Column(JSON)
    variable = Column(JSON)






def create_Tables(engine):
    #for tbl in reversed(Base.metadata.sorted_tables):
    #    try:
    #        engine.execute(tbl.delete())
    #    except:
    #        pass

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def insert_Hard_Coded(db):
    objects = []
    objects.append(Charge_Point(cp_id = "CP_1", password="passcp1"))
    objects.append(Charge_Point(cp_id = "CP_2", password="passcp1"))

    evse = EVSE(cp_id = "CP_1", evse_id = 1)
    evse2 = EVSE(cp_id = "CP_1", evse_id = 2)
    objects.append(evse)
    objects.append(evse2)

    #start button
    objects.append(IdToken(id_token = "", type=enums.IdTokenType.no_authorization))

    id_Token = IdToken(id_token = "123456789", type=enums.IdTokenType.iso14443)
    group_id_token = GroupIdToken(id_token = "group123456789", type=enums.IdTokenType.iso14443)
    
    objects.append(id_Token)
    objects.append(group_id_token)
    info = IdTokenInfo(
            id_token=id_Token, 
            language1="PT", 
            group_id_token=group_id_token,
            valid=True
            #cache_expiry_date_time = datetime.utcnow().isoformat()
            )
    info.evse.append(evse)
    objects.append(info)

    db.session.add_all(objects)
    db.session.commit()