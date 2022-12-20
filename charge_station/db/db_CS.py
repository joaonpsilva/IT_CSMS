import asyncio

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, update, select, delete, insert
from db_Tables_CS import *


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
            "UPDATE" : self.update
        }

        self.table_mapping={
            "LocalList":LocalList,
            "IdToken":IdToken,
            "GroupIdToken":GroupIdToken,
            "IdTokenInfo":IdTokenInfo
        }

    
    async def on_db_request(self, request):
        if request.intent in self.method_mapping:
            return self.method_mapping[request.intent](**request.__dict__)


    def select(self, content, **kwargs):
        if "filters" not in content:
            content["filters"] = {}
        statement = select(self.table_mapping[content["table"]]).filter_by(**content["filters"])
        return [obj.get_dict_obj() for obj in self.session.scalars(statement).all()]
    
    def create(self, content, **kwargs):
        statement = insert(self.table_mapping[content["table"]]).values(**content["values"])
        self.session.execute(statement)
    
    def remove(self, content, **kwargs):
        if "filters" not in content:
            content["filters"] = {}
        statement = delete(self.table_mapping[content["table"]]).filter_by(**content["filters"])
        self.session.execute(statement)

    def update(self, content, **kwargs):
        if "filters" not in content:
            content["filters"] = {}
        statement = update(self.table_mapping[content["table"]]).filter_by(**content["filters"]).values(**content["values"])
        self.session.execute(statement)



    async def run(self):

        #Initialize broker that will handle Rabbit coms
        self.broker = Fanout_Rabbit_Handler(self.on_db_request, "OCPPclientDB")
        #Start listening to messages
        await self.broker.connect()



if __name__ == '__main__':
    # Main part
    loop = asyncio.new_event_loop()

    loop.create_task(DataBase_CP().run())
    loop.run_forever()