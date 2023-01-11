import asyncio

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, update, select, delete, insert
from db_Tables_CS import *
import traceback
import argparse
import sys
from os import path
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
from fanout_Rabbit_Handler import Fanout_Rabbit_Handler
import logging
logging.basicConfig(level=logging.INFO)

class DataBase_CP:

    def __init__(self):
        #MySql engine
        self.engine = create_engine("mysql+pymysql://root:password123@localhost:3306/cs_db")
        logging.info("Connected to the database")

        #Create new sqlachemy session
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        #Create SQL tables
        create_Tables(self.engine)

        #Insert some CPs (testing)
        insert_Hard_Coded(self)


        #map incoming messages to methods
        self.method_mapping={
            "SELECT" : self.select,
            "CREATE" : self.create,
            "REMOVE" : self.remove,
            "UPDATE" : self.update,
            "SendLocalList" : self.updateLocalList,
            "get_IdToken_Info" : self.get_IdToken_Info
        }

        self.table_mapping={
            "LocalList":LocalList,
            "IdToken":IdToken,
            "IdTokenInfo":IdTokenInfo
        }

    
    async def on_db_request(self, request):
        if request.intent in self.method_mapping:
            try:
                toReturn = self.method_mapping[request.intent](**request.content)
                self.session.commit()
                return {"status":"OK", "content":toReturn}

            except:
                self.session.rollback()

                logging.error(traceback.format_exc())
                return {"status":"ERROR"}


    def select(self, table, filters={}, dict_format=True, **kwargs):
        statement = select(self.table_mapping[table]).filter_by(**filters)
        if dict_format:
            return [obj.get_dict_obj() for obj in self.session.scalars(statement).all()]
        return self.session.scalars(statement).all()
    
    def create(self, table,values,**kwargs):
        statement = insert(self.table_mapping[table]).values(**values)
        self.session.execute(statement)
    
    def remove(self, table,filters={}, **kwargs):
        statement = delete(self.table_mapping[table]).filter_by(**filters)
        self.session.execute(statement)

    def update(self, table, values, filters={}, **kwargs):
        statement = update(self.table_mapping[table]).filter_by(**filters).values(**values)
        self.session.execute(statement)
    

    def updateLocalList(self, version_number, update_type, local_authorization_list=[]):

        #start transaction
        with self.session.begin():
            
            current_version = self.select("LocalList")[-1]["version_number"]
            self.update("LocalList", filters={"version_number":current_version}, values={"version_number":version_number})

            if update_type == enums.UpdateType.full:
                self.remove("IdToken")
            
            for auth_data in local_authorization_list:
                if "id_token_info" in auth_data:
                    auth_data["id_token_info"].pop("status")
                    auth_data["id_token"]["id_token_info"] = auth_data["id_token_info"]

                    id_token = IdToken(**auth_data["id_token"])
                    self.session.merge(id_token)               
                else:
                    self.remove("IdToken", auth_data["id_token"])
        
    
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

                

    async def run(self, rabbit):

        #Initialize broker that will handle Rabbit coms
        self.broker = Fanout_Rabbit_Handler("OCPPclientDB", self.on_db_request)
        #Start listening to messages
        await self.broker.connect(rabbit)



if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("-rb", type=str, default = "amqp://guest:guest@localhost/", help="RabbitMq")
    args = parser.parse_args()

    # Main part
    loop = asyncio.new_event_loop()

    loop.create_task(DataBase_CP().run(args.rb))
    loop.run_forever()