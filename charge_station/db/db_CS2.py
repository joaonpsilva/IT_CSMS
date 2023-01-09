import sqlalchemy
from sqlalchemy import Column, ForeignKey, Integer, String, Table, Boolean, JSON, Enum, Float
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from ocpp.v201 import enums


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


class Component(Base):
    __tablename__ = "Component"
    id = Column(Integer, primary_key = True)

    enabled = Column(Boolean)
    name = Column(String)
    evse = Column(Integer)

    variables = relationship("Variable", backref="component")



class Variable(Base):
    __tablename__ = "Variable"
    id = Column(Integer, primary_key = True)

    name = Column(String)
    instance = Column(String)
    evse = Column(Integer)

    _componentId = Column(Integer, ForeignKey("Component.id"))

    variable_attributes = relationship("VariableAttribute", backref="variable")
    variable_characteristics = relationship("VariableCharacteristics", backref="variable", uselist=False)


class VariableAttribute(Base):
    __tablename__ = "VariableAttribute"
    id = Column(Integer, primary_key = True)

    type = Column(Enum(enums.AttributeType), default=enums.AttributeType.actual)
    value = Column(String(2500))
    mutability = Column(Enum(enums.MutabilityType))
    persistent = Column(Boolean)        #Needed?
    constant = Column(Boolean)

    _variableId = Column(Integer, ForeignKey("Variable.id"))


class VariableCharacteristics(Base):
    __tablename__ = "VariableCharacteristics"
    id = Column(Integer, primary_key = True)

    data_type = Column(Enum(enums.DataType))
    min_limit = Column(Float)
    max_limit = Column(Float)
    valuesList = Column(JSON)
    supports_monitoring = Column(Boolean)

    _variableId = Column(Integer, ForeignKey("Variable.id"))



class DataBase_CP2:
    def __init__(self):

        self.engine = sqlalchemy.create_engine("sqlite:///DB16.db")
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        Base.metadata.create_all(self.engine)

        #c = Component(name="DeviceDataCtrlr")
        #v = Variable(name="ItemsPerMessage", instance="GetVariables",component=c)
        #a = VariableAttribute(value = 50, variable=v)
        #self.session.add_all([c, v, a])
        #self.session.commit()


    def search_Variable(self, variable):
        return self.session.query(ocpp_standard_configuration).get(variable)

    
    def get_Variable_in_DB(self, component, variable, attribute_type=enums.AttributeType.actual):
        
        if "instance" in component:
            component.pop("instance")
        if "instance" not in variable:
            variable["instance"] = None

        statement = sqlalchemy.select(Component).filter_by(**component)

        try:
            component = self.session.scalars(statement).first()
        except:
            return enums.GetVariableStatusType.unknown_component, None

        value =None
        for var in component.variables:
            if var.name == variable["name"] and var.instance == variable["instance"]:
                for attribute in var.variable_attributes:
                    if attribute.type == attribute_type:
                        value = attribute.value
                        return enums.GetVariableStatusType.accepted, value 
                return enums.GetVariableStatusType.not_supported_attribute_type
        
        return enums.GetVariableStatusType.unknown_variable, None

            


    def setVariable(self, component, variable, attribute_value, attribute_type=enums.AttributeType.actual):
        
        if "instance" in component:
            component.pop("instance")
        if "instance" not in variable:
            variable["instance"] = None

        statement = sqlalchemy.select(Component).filter_by(**component)
        try:
            component = self.session.scalars(statement).first()
        except:
            return enums.SetVariableStatusType.unknown_component
        
        for var in component.variables:
            if var.name == variable["name"] and var.instance == variable["instance"]:
                for attribute in var.variable_attributes:
                    if attribute.type == attribute_type:
                        attribute.value = attribute_value
                        self.session.commit()
                        return enums.SetVariableStatusType.accepted
                return enums.SetVariableStatusType.not_supported_attribute_type
        
        return enums.SetVariableStatusType.unknown_variable

               


        
        

                


