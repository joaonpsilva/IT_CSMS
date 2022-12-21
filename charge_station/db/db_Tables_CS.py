from sqlalchemy.orm import declarative_base, relationship, backref
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Enum, ForeignKeyConstraint, Float, Table, Boolean, JSON
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
        return { attr:value for attr, value in self.__dict__.items() if not attr.startswith("_") and value is not None }



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

    def get_dict_obj(self):
        result = super().get_dict_obj()

        #check if belongs to a group
        if self.group_id_token is not None:
            result["group_id_token"] = self.group_id_token.get_dict_obj()
        
        return result




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