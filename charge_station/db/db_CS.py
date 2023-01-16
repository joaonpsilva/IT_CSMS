import sqlalchemy

import logging
logging.basicConfig(level=logging.INFO)

from sqlalchemy import create_engine, update, select, delete, insert
from sqlalchemy.orm import sessionmaker
from db.db_Tables_CS import *
import sys
from os import path
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
from fanout_Rabbit_Handler import Fanout_Rabbit_Handler
import logging
logging.basicConfig(level=logging.INFO)
import traceback


class DataBase_CP:
    def __init__(self):

        self.engine = sqlalchemy.create_engine("sqlite:///DB16.db")
        logging.info("Connected to the database")

        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        Base.metadata.create_all(self.engine)

        insert_Hard_Coded(self.session)


        self.table_mapping={
            "LocalList":LocalList,
            "IdToken":IdToken,
            "IdTokenInfo":IdTokenInfo,
            "GroupIdToken":GroupIdToken
        }

    
    def getVariable(self, component, variable, attribute_type=enums.AttributeType.actual):
        
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
        
        self.session.commit()

        return enums.SetVariableStatusType.unknown_variable




    def updateLocalList(self, version_number, update_type, local_authorization_list=[]):
        try:
        #start transaction
        #with self.session.begin():
            
            current_version = self.get_LocalList_Version()

            statement = update(LocalList).filter_by(version_number=current_version).values(version_number=version_number)
            self.session.execute(statement)


            if update_type == enums.UpdateType.full:
                self.session.execute(delete(GroupIdToken))
                self.session.execute(delete(IdTokenInfo))
                self.session.execute(delete(IdToken))
            
            for auth_data in local_authorization_list:
                if "id_token_info" in auth_data:
                    auth_data["id_token_info"].pop("status")
                    auth_data["id_token"]["id_token_info"] = auth_data["id_token_info"]

                    id_token = IdToken(**auth_data["id_token"])
                    self.session.merge(id_token)               
                else:
                    id_token = self.session.query(IdToken).filter_by(**auth_data["id_token"]).first()
                    self.session.delete(id_token)


            self.session.commit()
            return True
        except:
            logging.error(traceback.format_exc())
            self.session.rollback()
            return False
        
    
    def get_IdToken_Info(self, id_token, **kwargs):

        idToken = self.session.query(IdToken).get(id_token['id_token'])
        if idToken is None:
            return {"id_token" : None, "id_token_info" : None}

        #transform do dict
        idToken_dict = idToken.get_dict_obj()

        #get idtokeninfo from idtoken
        idTokenInfo = idToken.id_token_info
        #load groupid from info
        idTokenInfo.group_id_token
        #transform to dict
        idTokenInfo_dict = idTokenInfo.get_dict_obj()
        
        return {"id_token" : idToken_dict, "id_token_info" : idTokenInfo_dict}
    

    def get_LocalList_Version(self):
        locallist = self.session.scalars(select(LocalList)).first()
        return locallist.version_number
    

    def store_Queued_Messages(self, queued_messages):
        for m in queued_messages:
            m = QueuedMessages(message_type=m.__class__.__name__, payload=m.__dict__)
            self.session.add(m)
        self.session.commit()
    

    def get_Queued_Messages(self):
        to_return = []
        for m in self.session.scalars(select(QueuedMessages)).all():
            to_return.append(m.to_ocppPayload())
            self.session.delete(m)
        
        self.session.commit()
        return to_return

