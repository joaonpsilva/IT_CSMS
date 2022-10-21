from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Enum, ForeignKeyConstraint, Float
from sqlalchemy.orm import declarative_base, relationship
from ocpp.v201 import enums


Base = declarative_base()

class Charge_Point(Base):
    __tablename__ = "Charge_point"
    id = Column(String, primary_key=True)
    password = Column(String)
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
    meterValues = relationship("MeterValue", backref="EVSE")



class Connector(Base):
    __tablename__ = "Connector"
    cp_id = Column(Integer, primary_key=True)
    evse_id = Column(Integer, primary_key=True)
    connector_id = Column(Integer, primary_key=True) #This id is only unique inside each EVSE
    connector_status = Column(Enum(enums.ConnectorStatusType))

    __table_args__ = (ForeignKeyConstraint(["cp_id", "evse_id"],
                                            [ "EVSE.cp_id", "EVSE.evse_id"]),
                        {})


class MeterValue(Base):
    __tablename__ = "MeterValue"
    id = Column(Integer, primary_key=True)
    cp_id = Column(Integer)
    evse_id = Column(Integer)
    __table_args__ = (ForeignKeyConstraint(["cp_id", "evse_id"],
                                            [ "EVSE.cp_id", "EVSE.evse_id"]),
                        {})
    timestamp = Column(DateTime)

    value = Column(Float, nullable=False)
    context = Column(Enum(enums.ReadingContextType))
    measurand = Column(Enum(enums.MeasurandType))
    phase = Column(Enum(enums.PhaseType))
    location = Column(Enum(enums.LocationType))
    #signed_meter_value = 
    #unit_of_measure = 




def create_Tables(engine):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)