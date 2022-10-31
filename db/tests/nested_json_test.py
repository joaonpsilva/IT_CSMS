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
    name_pet = Column(String(50))

    owner = relationship("Owner", backref="pets", uselist=False)

Base.metadata.create_all(engine)


# Map keys to classes
mapping = {frozenset(('name', '')): Owner,
           frozenset(('name_pet', 'owner')): Pet}

def class_mapper(d):
    for keys, cls in mapping.items():
        #print(keys)
        #print(d.keys())
        #print(keys.issuperset(d.keys()))
        if keys.issuperset(d.keys()):
            return cls(**d)
    else:
        pass



data = '{"name_pet": "nina", "owner": {"name": "joao"}}'

nina = json.loads(data, object_hook=class_mapper)
print(nina.name_pet)
print(nina.owner.name)

session.add(nina)
session.commit()

