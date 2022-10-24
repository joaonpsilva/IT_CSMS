from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Enum, ForeignKeyConstraint, Float
from sqlalchemy.orm import declarative_base, relationship
from ocpp.v201 import enums
from passlib.context import CryptContext

PASSLIB_CONTEXT = CryptContext(
    # in a new application with no previous schemes, start with pbkdf2 SHA512
    schemes=["pbkdf2_sha512"],
    deprecated="auto",
)

Base = declarative_base()

class Charge_Point(Base):
    __tablename__ = "Charge_point"
    id = Column(String(20), primary_key=True)
    password_hash = Column(String(256)) #https://stackoverflow.com/questions/56738384/sqlalchemy-call-function-and-save-returned-value-in-table-always
    model = Column(String(20))
    vendor_name = Column(String(50))
    serial_number = Column(String(25))
    firmware_version = Column(String(50))
    modem_iccid = Column(String(20))
    modem_imsi = Column(String(20))

    evses = relationship("EVSE", backref="Charge_point")

    def __init__(self, password, **kwargs):
        
        password_hash = self.generate_hash(password)
        super().__init__(password_hash=password_hash, **kwargs)
    
    @property
    def password(self):
        raise AttributeError("User.password is write-only")
    
    @password.setter
    def password(self, password):
        self.password_hash = self.generate_hash(password)
    
    @staticmethod
    def generate_hash(password):
        """Generate a secure password hash from a new password"""
        return PASSLIB_CONTEXT.hash(password.encode("utf8"))
    
    def verify_password(self, password):
        return PASSLIB_CONTEXT.verify(password, self.password_hash)




class EVSE(Base):
    __tablename__ = "EVSE"
    cp_id = Column(String(20), ForeignKey("Charge_point.id"), primary_key=True)
    evse_id = Column(Integer, primary_key=True)   #This id is only unique inside each CP

    connectors = relationship("Connector", backref="EVSE")
    meterValues = relationship("MeterValue", backref="EVSE")



class Connector(Base):
    __tablename__ = "Connector"
    cp_id = Column(String(20), primary_key=True)
    evse_id = Column(Integer, primary_key=True)
    connector_id = Column(Integer, primary_key=True) #This id is only unique inside each EVSE
    connector_status = Column(Enum(enums.ConnectorStatusType))

    __table_args__ = (ForeignKeyConstraint(["cp_id", "evse_id"],
                                            [ "EVSE.cp_id", "EVSE.evse_id"]),
                        {})


class MeterValue(Base):
    __tablename__ = "MeterValue"
    id = Column(Integer, primary_key=True)
    cp_id = Column(String(20))
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