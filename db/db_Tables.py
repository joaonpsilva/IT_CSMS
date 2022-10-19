from sqlalchemy import Column, ForeignKey, Integer, String, Table, create_engine, Enum, ForeignKeyConstraint
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
    cp_id = Column(Integer, ForeignKey("Charge_point.id"), primary_key=True)
    evse_id = Column(Integer, primary_key=True)   #This id is only unique inside each CP

    connectors = relationship("Connector", backref="EVSE")



class Connector(Base):
    __tablename__ = "Connector"
    cp_id = Column(Integer, primary_key=True)
    evse_id = Column(Integer, primary_key=True)
    connector_id = Column(Integer, primary_key=True) #This id is only unique inside each EVSE
    connector_status = Enum(enums.ConnectorStatusType)

    __table_args__ = (ForeignKeyConstraint(["cp_id", "evse_id"],
                                            [ "EVSE.cp_id", "EVSE.evse_id"]),
                        {})



def create_Tables(engine):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)