#TEST SCRIPT, UNRELATED

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
    pets = relationship("Pet", backref="owner")


class Pet(Base):
    __tablename__ = "pet"
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    owner_id = Column(Integer, ForeignKey("owner.id"))

Base.metadata.create_all(engine)



#INSERIR
joao = Owner(id = 9, name="Joao")
session.add(joao)

nina = Pet(name="Nina", owner=joao)

print(nina.owner.name)
print(joao.pets[0].name)

session.add(nina)
session.commit()

o = Owner(id = 9, name="Joao")
nina = Pet(name="Nina", owner=o)

session.merge(nina)
session.commit()




