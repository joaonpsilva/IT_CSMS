from sqlalchemy import Column, ForeignKey, Integer, String, Table, create_engine, Enum
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from ocpp.v201 import enums


Base = declarative_base()

class Charge_Point(Base):
    __tablename__ = "Charge_point"
    id = Column(Integer, primary_key=True)
    model = Column(String(20), nullable=False)
    vendor_name = Column(String(50), nullable=False)
    serial_number = Column(String(25))
    firmware_version = Column(String(50))
    modem_iccid = Column(String(20))
    modem_imsi = Column(String(20))

    evses = relationship("EVSE", backref="Charge_point")


class EVSE(Base):
    __tablename__ = "EVSE"
    id = Column(Integer, primary_key=True)
    evse_id = Column(Integer, nullable=False)
    cp_id = Column(Integer, ForeignKey("Charge_point.id"))

    connectors = relationship("Connector", backref="EVSE")



class Connector(Base):
    __tablename__ = "Connector"
    id = Column(Integer, primary_key=True)
    connector_id = Column(Integer, nullable=False)
    evse_id = Column(Integer, ForeignKey("EVSE.id"))
    connectorStatus = Enum(enums.ConnectorStatusType)



def create_Tables(engine):
    Base.metadata.create_all(engine)