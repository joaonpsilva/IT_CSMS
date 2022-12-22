from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Enum, ForeignKeyConstraint, Float, Table, Boolean, JSON
from sqlalchemy.orm import declarative_base, relationship, backref
from ocpp.v201 import enums


Base = declarative_base()

class CustomBase(Base):
    """Base extender
    In sqlalchemy we can init an obj and pass a relation throw passing another object in the init
    This extender allows to also pass a dict with the correct fields for creating that object
    """
    __abstract__ = True

    def __init__(self, **kwargs):

        for arg in kwargs:
            if arg in self.__mapper__.relationships.keys():
                rel = self.__mapper__.relationships[arg] 

                if rel.uselist:                    
                    o = [rel.mapper.class_(**d_l) if not isinstance(d_l, rel.mapper.class_) else d_l for d_l in kwargs[arg]]
                else:
                    if isinstance(kwargs[arg], rel.mapper.class_):
                        continue
                    o = rel.mapper.class_(**kwargs[arg])
                
                kwargs[arg] = o


        super().__init__(**kwargs)
    
    def get_dict_obj(self):
        return { attr:value 
            if attr not in self.__mapper__.relationships.keys() else value.get_dict_obj() 
            for attr, value in self.__dict__.items() 
            if not attr.startswith("_")}