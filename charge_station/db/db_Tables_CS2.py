import sqlalchemy
from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import declarative_base, relationship, sessionmaker


engine = sqlalchemy.create_engine("sqlite:///DB16.db")
Session = sessionmaker(bind=engine)
session = Session()
Base = declarative_base()

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


statement = sqlalchemy.select(ocpp_standard_configuration)
print(len(session.scalars(statement).all()))
