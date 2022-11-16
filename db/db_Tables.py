from xmlrpc.client import Boolean
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Enum, ForeignKeyConstraint, Float, Table, Boolean, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship, backref
from ocpp.v201 import enums
from passlib.context import CryptContext
from datetime import datetime
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.inspection import inspect

PASSLIB_CONTEXT = CryptContext(
    # in a new application with no previous schemes, start with pbkdf2 SHA512
    schemes=["pbkdf2_sha512"],
    deprecated="auto",
)

Base = declarative_base()

"""class Table_Factory:

    session = None

    def get_or_Create(table_class, **kwargs):
"""

class CustomBase(Base):
    __abstract__ = True

    def __init__(self, **kwargs):

        for arg in kwargs:
            if arg in self.__mapper__.relationships.keys():
                rel = self.__mapper__.relationships[arg] 

                if isinstance(kwargs[arg], rel.mapper.class_):
                    continue

                if rel.uselist:                    
                    o = [rel.mapper.class_(**d_l) for d_l in kwargs[arg]]
                else:
                    o = rel.mapper.class_(**kwargs[arg])
                
                kwargs[arg] = o


        super().__init__(**kwargs)
    
    def get_dict_obj(self):
        return { attr:value for attr, value in self.__dict__.items() if not attr.startswith("_") and value is not None }



evse_idTokens = Table(
    'evse_idTokens',
    Base.metadata,
    Column('cp_id', String(20)),
    Column('evse_id', Integer),
    Column('id_token', String(36), ForeignKey('IdTokenInfo._id_token')),
    ForeignKeyConstraint(("cp_id", "evse_id"),
                        ("EVSE.cp_id", "EVSE.evse_id"))
)

evse_chargeProfiles = Table(
    'evse_chargeProfiles',
    Base.metadata,
    Column('cp_id', String(20)),
    Column('evse_id', Integer),
    Column('id', Integer, ForeignKey('ChargingProfile.id')),
    ForeignKeyConstraint(("cp_id", "evse_id"),
                        ("EVSE.cp_id", "EVSE.evse_id"))
)


class Modem(Base):
    __tablename__ = "Modem"
    iccid = Column(String(20), primary_key=True)
    imsi = Column(String(20), primary_key=True)

    def __init__(self, iccid="NULL", imsi="NULL", **kwargs):
        kwargs["iccid"] = iccid
        kwargs["imsi"] = imsi

        super().__init__(**kwargs)


class Charge_Point(CustomBase):
    __tablename__ = "Charge_point"
    cp_id = Column(String(20), primary_key=True)
    password_hash = Column(String(256)) #https://stackoverflow.com/questions/56738384/sqlalchemy-call-function-and-save-returned-value-in-table-always
    model = Column(String(20))
    vendor_name = Column(String(50))
    serial_number = Column(String(25))
    firmware_version = Column(String(50))

    _modem_iccid = Column(String(20))
    _modem_imsi = Column(String(20))
    __table_args__ = (ForeignKeyConstraint(["_modem_iccid", "_modem_imsi"],
                                            [ "Modem.iccid", "Modem.imsi"]),
                        {})
    modem = relationship("Modem", backref="charge_point")

    def __init__(self, password=None, **kwargs):
        
        if password:
            password_hash = self.generate_hash(password) #Encript password (Hash)
            kwargs["password_hash"] = password_hash
        
        super().__init__(**kwargs)
    
    @property
    def password(self):
        raise AttributeError("User.password is write-only")
    
    @password.setter
    def password(self, password):
        self.password_hash = self.generate_hash(password)
    
    @staticmethod
    def generate_hash(password):
        """Generate a secure password hash from a new password"""
        return PASSLIB_CONTEXT.hash(password.encode("utf8"))
    
    def verify_password(self, password):
        return PASSLIB_CONTEXT.verify(password, self.password_hash)


class EVSE(Base):
    __tablename__ = "EVSE"
    evse_id = Column(Integer, primary_key=True)   #This id is only unique inside each CP

    cp_id = Column(String(20), ForeignKey("Charge_point.cp_id"), primary_key=True)
    charge_point = relationship("Charge_Point", backref="evse")

    

    def __init__(self, id = None, **kwargs):
        if id:
            kwargs["evse_id"] = id
        super().__init__(**kwargs)


class Connector(Base):
    __tablename__ = "Connector"

    connector_id = Column(Integer, primary_key=True) #This id is only unique inside each EVSE
    connector_status = Column(Enum(enums.ConnectorStatusType))
    timestamp = Column(DateTime)

    cp_id = Column(String(20), primary_key=True)
    evse_id = Column(Integer, primary_key=True)
    __table_args__ = (ForeignKeyConstraint(["cp_id", "evse_id"],
                                            [ "EVSE.cp_id", "EVSE.evse_id"]),
                        {})
    evse = relationship("EVSE", backref="connector")


    def __init__(self,id=None,**kwargs):
        if id:
            kwargs["evse_id"] = id
        kwargs["evse"] = EVSE(cp_id=kwargs["cp_id"], evse_id = kwargs["evse_id"])
        super().__init__(**kwargs)




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
                                    [ "EVSE.cp_id", "EVSE.evse_id"]),
                    ForeignKeyConstraint(["transaction_id", "seq_no"],
                                    [ "Transaction_Event.transaction_id", "Transaction_Event.seq_no"]),{})


class SignedMeterValue(Base):
    __tablename__ = "SignedMeterValue"
    id = Column(Integer, primary_key=True)
    signed_meter_data = Column(String(2500))
    signing_method = Column(String(50))
    encoding_method = Column(String(50))
    public_key = Column(String(2500))


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

    _signed_meter_value_id = Column(Integer, ForeignKey("SignedMeterValue.id"))
    signed_meter_value = relationship("SignedMeterValue", backref=backref("sampled_value", uselist=False), uselist=False)

    def __init__(self, unit_of_measure=None, **kwargs):
        if unit_of_measure:
            for key, value in unit_of_measure.items():
                kwargs[key] = value

        super().__init__(**kwargs)


    

class IdToken(CustomBase):
    __tablename__ = "IdToken"
    id_token = Column(String(36), primary_key=True)
    type = Column(Enum(enums.IdTokenType))


class GroupIdToken(CustomBase):
    __tablename__ = "GroupIdToken"
    id_token = Column(String(36), primary_key=True)
    type = Column(Enum(enums.IdTokenType))


class IdTokenInfo(CustomBase):
    __tablename__ = "IdTokenInfo"

    _id_token = Column(String(36), ForeignKey("IdToken.id_token"), primary_key=True)
    id_token = relationship("IdToken", backref=backref("id_token_info", uselist=False), uselist=False)

    cache_expiry_date_time = Column(DateTime)
    charging_priority = Column(Integer)
    language_1 = Column(String(8))
    language_2 = Column(String(8))
    evse = relationship('EVSE', secondary=evse_idTokens, backref='id_token_info')
    
    _group_id_token = Column(String(36), ForeignKey("GroupIdToken.id_token"))
    group_id_token = relationship("GroupIdToken", backref="id_token_info", uselist=False)

    def get_dict_obj(self):
        result = super().get_dict_obj()

        #check if belongs to a group
        if self.group_id_token is not None:
            result["group_id_token"] = self.group_id_token.get_dict_obj()
        
        return result
    
    def get_allowed_evse_for_cp(self, cp_id):
            
        #get evse in which can charge in this cp
        return [evse.evse_id for evse in self.evse if evse.cp_id == cp_id]            
        



class Transaction(CustomBase):
    __tablename__ = "Transaction"
    transaction_id = Column(String(36), primary_key=True)
    charging_state = Column(Enum(enums.ChargingStateType))
    time_spent_charging = Column(Integer)
    stopped_reason = Column(Enum(enums.ReasonType))
    remote_start_id = Column(Integer, unique=True)

    

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

    #CP, EVSE, Connector
    cp_id = Column(String(20), ForeignKey("Charge_point.cp_id"))
    connector_id = Column(Integer)
    evse_id = Column(Integer)

    __table_args__ = (ForeignKeyConstraint(["cp_id", "evse_id"],
                                [ "EVSE.cp_id", "EVSE.evse_id"]),
                ForeignKeyConstraint(["cp_id", "evse_id", "connector_id"],
                                [ "Connector.cp_id", "Connector.evse_id", "Connector.connector_id"]),{})

    charge_point = relationship("Charge_Point", backref="transaction", uselist=False)
    evse = relationship("EVSE", backref=backref("transaction", overlaps="charge_point,transaction"), uselist=False, overlaps="charge_point,transaction")
    connector = relationship("Connector", backref=backref("transaction", overlaps="charge_point,evse,transaction"), uselist=False, overlaps="charge_point,evse,transaction")


    #Transaction
    transaction_id = Column(String(36), ForeignKey("Transaction.transaction_id"), primary_key = True)
    transaction_info = relationship("Transaction", backref="transaction_event",uselist=False)

    #Meter value
    meter_value = relationship("MeterValue", backref="transaction_event", uselist=False)



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
    transaction_info = relationship("Transaction", backref="charging_profile",uselist=False)

    charging_schedule = relationship("ChargingSchedule", backref="charging_profile")

    evse = relationship('EVSE', secondary=evse_chargeProfiles, backref='charging_profile')



"""do i need this?"""
class ChargingSchedule(CustomBase):
    __tablename__ = "ChargingSchedule"

    id = Column(Integer, primary_key = True)
    start_schedule = Column(DateTime)
    duration = Column(Integer)
    charging_rate_unit = Column(Enum(enums.ChargingRateUnitType))
    min_charging_rate = Column(Float)

    _charging_profile = Column(Integer, ForeignKey("ChargingProfile.id"))

    charging_schedule_period = relationship("ChargingSchedulePeriod", backref="charging_schedule")
    sales_tariff = relationship("SalesTariff", uselist=False, backref="charging_schedule")


class ChargingSchedulePeriod(Base):
    __tablename__ = "ChargingSchedulePeriod"

    id = Column(Integer, primary_key = True)
    start_period = Column(Integer)
    limit = Column(Float)
    number_phases = Column(Integer)
    phase_to_use = Column(Integer)

    _charging_schedule = Column(Integer, ForeignKey("ChargingSchedule.id"))


class SalesTariff(Base):
    __tablename__ = "SalesTariff"
    id = Column(Integer, primary_key = True)
    content = Column(String(1000))

    _charging_schedule = Column(Integer, ForeignKey("ChargingSchedule.id"))

    def __init__(self, id , **kwargs):
        content = str(kwargs)
        kwargs = {"id":id, "content":content}
        super().__init__(**kwargs)













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
    objects.append(evse)

    #start button
    objects.append(IdToken(id_token = "", type=enums.IdTokenType.no_authorization))

    id_Token = IdToken(id_token = "123456789", type=enums.IdTokenType.iso14443)
    group_id_token = GroupIdToken(id_token = "group123456789", type=enums.IdTokenType.iso14443)
    
    objects.append(id_Token)
    objects.append(group_id_token)
    info = IdTokenInfo(
            id_token=id_Token, 
            language_1="PT", 
            group_id_token=group_id_token,
            #cache_expiry_date_time = datetime.utcnow().isoformat()
            )
    info.evse.append(evse)
    objects.append(info)

    db.session.add_all(objects)
    db.session.commit()