from sqlalchemy.orm import declarative_base, relationship, backref
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Enum, ForeignKeyConstraint, Float, Table, Boolean, JSON
from ocpp.v201 import enums

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

    id_token_info = relationship("IdTokenInfo", backref=backref("id_token", uselist=False), uselist=False)


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

    _id_token = Column(String(36), ForeignKey("IdToken.id_token",ondelete='CASCADE'), primary_key=True)
    
    _group_id_token = Column(String(36), ForeignKey("GroupIdToken.id_token"))
    group_id_token = relationship("GroupIdToken", backref="id_token_info", uselist=False)



def create_Tables(engine):
    #for tbl in reversed(Base.metadata.sorted_tables):
    #    try:
    #        engine.execute(tbl.delete())
    #    except:
    #        pass

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def insert_Hard_Coded(db):
    objects=[]

    objects.append(
        LocalList(version_number=0)
    )
    db.session.add_all(objects)
    db.session.commit()