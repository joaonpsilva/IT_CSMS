from sqlalchemy.orm import declarative_base, relationship, backref
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Enum, ForeignKeyConstraint, Float, Table, Boolean, JSON, BINARY
from ocpp.v201 import enums, call

import sys
from os import path
sys.path.append( path.dirname(path.dirname( path.dirname( path.abspath(__file__) ) ) ))

from database_Base import *

class LocalList(CustomBase):
    __tablename__ = "LocalList"
    version_number = Column(Integer, autoincrement=False, primary_key=True)

    id_tokens = relationship("IdToken")


class IdToken(CustomBase):
    __tablename__ = "IdToken"
    id_token = Column(String(36), primary_key=True)
    type = Column(Enum(enums.IdTokenType))

    version_number = Column(Integer, ForeignKey('LocalList.version_number'))

    id_token_info = relationship("IdTokenInfo", cascade="all,delete-orphan", backref=backref("id_token", uselist=False), uselist=False)


class GroupIdToken(CustomBase):
    __tablename__ = "GroupIdToken"
    id_token = Column(String(36), primary_key=True)
    type = Column(Enum(enums.IdTokenType))


class IdTokenInfo(CustomBase):
    __tablename__ = "IdTokenInfo"

    cache_expiry_date_time = Column(DateTime)
    charging_priority = Column(Integer)
    language1 = Column(String(8))
    language2 = Column(String(8))
    evse_id = Column(JSON)

    _id_token = Column(String(36), ForeignKey("IdToken.id_token"), primary_key=True)
    
    _group_id_token = Column(String(36), ForeignKey("GroupIdToken.id_token"))
    group_id_token = relationship("GroupIdToken", backref="id_token_info", uselist=False)


############

class ocpp_standard_configuration(Base):
    __tablename__ = "ocpp_standard_configuration"

    NAME = Column(String, primary_key=True)
    Accessibility = Column(String)
    type = Column(String)
    Unit = Column(String)
    Value = Column(String)
    isOcppKey = Column(Integer)
    Public = Column(Integer)
    OnBoot = Column(Integer)
    inSM = Column(Integer)
    minValue = Column(Integer)
    maxValue = Column(Integer)


class Component(Base):
    __tablename__ = "Component"
    id = Column(Integer, primary_key = True)

    enabled = Column(Boolean)
    name = Column(String)
    evse_id = Column(Integer)
    connector_id = Column(Integer)

    variables = relationship("Variable", backref="component")

    def __init__(self, evse=None, **kwargs):
        if evse:
            kwargs["evse_id"] = evse["id"]
            kwargs["connector_id"] = evse["connector_id"]
            super().__init__(**kwargs)


class Variable(Base):
    __tablename__ = "Variable"
    id = Column(Integer, primary_key = True)

    name = Column(String)
    instance = Column(String)
    evse = Column(Integer)

    _componentId = Column(Integer, ForeignKey("Component.id"))

    variable_attributes = relationship("VariableAttribute", backref="variable")
    variable_characteristics = relationship("VariableCharacteristics", backref="variable", uselist=False)


class VariableAttribute(Base):
    __tablename__ = "VariableAttribute"
    id = Column(Integer, primary_key = True)

    type = Column(Enum(enums.AttributeType), default=enums.AttributeType.actual)
    value = Column(String(2500))
    mutability = Column(Enum(enums.MutabilityType))
    persistent = Column(Boolean)        #Needed?
    constant = Column(Boolean)

    _variableId = Column(Integer, ForeignKey("Variable.id"))


class VariableCharacteristics(Base):
    __tablename__ = "VariableCharacteristics"
    id = Column(Integer, primary_key = True)

    data_type = Column(Enum(enums.DataType))
    min_limit = Column(Float)
    max_limit = Column(Float)
    valuesList = Column(JSON)
    supports_monitoring = Column(Boolean)

    _variableId = Column(Integer, ForeignKey("Variable.id"))



class QueuedMessages(Base):
    __tablename__ = "QueuedMessages"

    id = Column(Integer, primary_key = True)
    message_type = Column(String)
    payload = Column(JSON)

    def to_ocppPayload(self):
        return getattr(call, self.message_type)(**self.payload)



def insert_Hard_Coded(session):
    """objects=[]

    objects.append(
        LocalList(version_number=0)
    )
    session.add_all(objects)
    session.commit()"""
    return
