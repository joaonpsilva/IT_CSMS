import json
import sqlalchemy
from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

engine = sqlalchemy.create_engine("sqlite:///teste.db")
Session = sessionmaker(bind=engine)
session = Session()
Base = declarative_base()

#CRIAR TABELAS
class Owner(Base):
    __tablename__ = "owner"
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    pet_id = Column(Integer, ForeignKey("pet.id"))


class Pet(Base):
    __tablename__ = "pet"
    id = Column(Integer, primary_key=True)
    name = Column(String(50))

    owner = relationship("Owner", backref="pets")

    def __init__(self, owner=None, **kwargs):
        if owner:
            o_l = []
            for o in owner:
                o = Owner(**o)
                o_l.append(o)
                kwargs["owner"] = o_l

        super().__init__(**kwargs)


Base.metadata.create_all(engine)


# Map keys to classes
mapping = {frozenset(['name']): Owner,
           frozenset(('id', 'name', 'owner')): Pet}

def class_mapper(d):
    for keys, cls in mapping.items():
        #print(keys)
        #print(d.keys())
        #print(keys.issuperset(d.keys()))
        if keys.issuperset(d.keys()):
            return cls(**d)
    else:
        pass



data = {"id": 1,"name":"aaa", "owner": [{"name": "jaojao"}]}

#nina = json.loads(data, object_hook=class_mapper)
nina = Pet(**data)

session.merge(nina)
session.commit()
print(nina.name)
print(nina.owner)

