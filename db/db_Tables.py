from numbers import Integral
from xmlrpc.client import Boolean
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Enum, ForeignKeyConstraint, Float, Table, Boolean
from sqlalchemy.orm import declarative_base, relationship, backref
from ocpp.v201 import enums
from passlib.context import CryptContext
from datetime import datetime

PASSLIB_CONTEXT = CryptContext(
    # in a new application with no previous schemes, start with pbkdf2 SHA512
    schemes=["pbkdf2_sha512"],
    deprecated="auto",
)

Base = declarative_base()

evse_idTokens = Table(
    'evse_idTokens',
    Base.metadata,
    Column('cp_id', String(20)),
    Column('evse_id', Integer),
    Column('id_token', String(36), ForeignKey('IdTokenInfo._id_token')),
    ForeignKeyConstraint(("cp_id", "evse_id"),
                        ("EVSE.cp_id", "EVSE.evse_id"))
)




class Charge_Point(Base):
    __tablename__ = "Charge_point"
    cp_id = Column(String(20), primary_key=True)
    password_hash = Column(String(256)) #https://stackoverflow.com/questions/56738384/sqlalchemy-call-function-and-save-returned-value-in-table-always
    model = Column(String(20))
    vendor_name = Column(String(50))
    serial_number = Column(String(25))
    firmware_version = Column(String(50))
    modem_iccid = Column(String(20))
    modem_imsi = Column(String(20))

    def __init__(self, password, **kwargs):
        
        password_hash = self.generate_hash(password)
        super().__init__(password_hash=password_hash, **kwargs)
    
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
    Charge_Point = relationship("Charge_Point", backref="EVSEs")



class Connector(Base):
    __tablename__ = "Connector"

    connector_id = Column(Integer, primary_key=True) #This id is only unique inside each EVSE
    connector_status = Column(Enum(enums.ConnectorStatusType))

    cp_id = Column(String(20), primary_key=True)
    evse_id = Column(Integer, primary_key=True)
    __table_args__ = (ForeignKeyConstraint(["cp_id", "evse_id"],
                                            [ "EVSE.cp_id", "EVSE.evse_id"]),
                        {})
    EVSE = relationship("EVSE", backref="Connectors")



class MeterValue(Base):
    __tablename__ = "MeterValue"
    id = Column(Integer, primary_key=True)

    cp_id = Column(String(20))
    evse_id = Column(Integer)
    __table_args__ = (ForeignKeyConstraint(["cp_id", "evse_id"],
                                            [ "EVSE.cp_id", "EVSE.evse_id"]),
                        {})
    EVSE = relationship("EVSE", backref="MeterValues")

    timestamp = Column(DateTime)

    value = Column(Float, nullable=False)
    context = Column(Enum(enums.ReadingContextType))
    measurand = Column(Enum(enums.MeasurandType))
    phase = Column(Enum(enums.PhaseType))
    location = Column(Enum(enums.LocationType))
    #signed_meter_value = 
    #unit_of_measure = 

class IdToken(Base):
    __tablename__ = "IdToken"
    id_token = Column(String(36), primary_key=True)
    type = Column(Enum(enums.IdTokenType))


class GroupIdToken(Base):
    __tablename__ = "GroupIdToken"
    id_token = Column(String(36), primary_key=True)
    type = Column(Enum(enums.IdTokenType))


class IdTokenInfo(Base):
    __tablename__ = "IdTokenInfo"

    _id_token = Column(String(36), ForeignKey("IdToken.id_token"), primary_key=True)
    IdToken = relationship("IdToken", backref=backref("IdTokenInfo", uselist=False), uselist=False)

    cache_expiry_date_time = Column(DateTime)
    charging_priority = Column(Integer)
    language_1 = Column(String(8))
    language_2 = Column(String(8))
    EVSEs = relationship('EVSE', secondary=evse_idTokens, backref='IdTokenInfos')
    
    _group_id_token = Column(String(36), ForeignKey("GroupIdToken.id_token"))
    GroupIdToken = relationship("GroupIdToken", backref="IdTokenInfos", uselist=False)





def create_Tables(engine):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def insert_Hard_Coded(db):
    objects = []
    objects.append(Charge_Point(id = "CP_1", password="passcp1"))
    objects.append(Charge_Point(id = "CP_2", password="passcp2"))

    id_Token = IdToken(id_token = "123456789", type=enums.IdTokenType.iso14443)
    group_id_token = GroupIdToken(id_token = "group123456789", type=enums.IdTokenType.iso14443)
    
    objects.append(id_Token)
    objects.append(group_id_token)
    objects.append(IdTokenInfo(
            IdToken=id_Token, 
            language_1="PT", 
            GroupIdToken=group_id_token
            #cache_expiry_date_time = datetime.utcnow().isoformat()
            ))



    db.session.add_all(objects)
    db.session.commit()