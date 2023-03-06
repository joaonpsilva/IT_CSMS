import logging
import websockets
import asyncio
from ocpp.v201 import call, call_result, enums, datatypes
from ocpp.v201 import ChargePoint as cp
from datetime import datetime
import random
from Transaction_simulation import Transaction
from aioconsole import ainput
from ocpp.routing import after,on
logging.basicConfig(level=logging.INFO)
import random
import argparse
import signal

class ChargePoint(cp):

    def __init__(self, id, connection, p, f):
        super().__init__(id, connection)

        self.period = p
        self.factor = f

        self.loop = asyncio.get_running_loop()
        self.evses = {
            1: {"connectors" : [1,2], "transaction_id":None},
            2: {"connectors" : [1,2,3], "transaction_id":None},
            3: {"connectors" : [1,2], "transaction_id":None}
        }

        self.active_transactions = {}
        self.shut_down_flag = asyncio.Event()
    

    def shut_down(self, sig=None, frame=None):
        self.shut_down_flag.set()


    async def wait_shut_down(self):
        await self.shut_down_flag.wait()
     
        for i, t in self.active_transactions.items():
            await t.end_event()
        
        exit(0)


    async def cold_Boot(self):

        request = call.BootNotificationPayload(
                    charging_station=datatypes.ChargingStationType(
                        vendor_name="vendor_name",
                        model="model"
                    ),
                    reason=enums.BootReasonType.power_up
                )

        response = await self.call(request)

        if response.status == 'Accepted':
           logging.info("Connected to central system.")

        for evse, info in self.evses.items():
            for connector in info["connectors"]:
                request = call.StatusNotificationPayload(
                    timestamp=datetime.utcnow().isoformat(),
                    evse_id=evse,
                    connector_id=connector,
                    connector_status=enums.ConnectorStatusType.available
                )
                response = await self.call(request)

        await self.random_simulation()
            

    async def random_simulation(self):
        
        while True:

            available_evses = [evse for evse, info in self.evses.items() if info["transaction_id"] is None]
            if len(available_evses) > 0:
                
                if random.random() > 0.6:
                    self.loop.create_task(self.make_transaction())

            await asyncio.sleep(5 * 60 / self.factor)


    async def make_transaction(self):

        available_evses = [evse for evse, info in self.evses.items() if info["transaction_id"] is None]

        if len(available_evses) == 0:
            logging.info("There are no free evses")
            return
        
        evse_id = random.choice(available_evses)
        connector_id = random.choice(self.evses[evse_id]["connectors"])

        transaction = Transaction(evse_id, connector_id, self.call, self.period, self.factor)
        self.active_transactions[transaction.transaction_id] = transaction
        self.evses[evse_id]["transaction_id"] = transaction.transaction_id

        await transaction.start_event()
        await transaction.authorize_event()
        await transaction.charging_events()
        await transaction.end_event()

        self.active_transactions.pop(transaction.transaction_id)
        self.evses[evse_id]["transaction_id"] = None
    

    @on("SetChargingProfile")
    async def on_SetChargingProfile(self, evse_id, charging_profile):

        charging_profile = datatypes.ChargingProfileType(**charging_profile)

        if charging_profile.transaction_id is not None:
            self.active_transactions[charging_profile.transaction_id].new_charge_values.set_result("XXXXXXXX")

        return call_result.SetChargingProfilePayload(status=enums.ChargingProfileStatus.accepted)

    @on("GetChargingProfiles")
    async def on_GetChargingProfiles(self, request_id, charging_profile, **kwargs):
        return call_result.GetChargingProfilesPayload(status=enums.GetChargingProfileStatusType.no_profiles)
    

    @on("DataTransfer")
    async def on_DataTransfer(self, data, **kwargs):            
        return call_result.DataTransferPayload(status=enums.DataTransferStatusType.accepted)

    @after("DataTransfer")
    async def after_DataTransfer(self, data, **kwargs):
        transaction_id = self.evses[data["evse_id"]]["transaction_id"]
        transaction = self.active_transactions[transaction_id]

        if "v2g_action" in data:
            await transaction.set_charging_action(data["v2g_action"]["action"])
            
        if "change_profile" in data:
            if "max_soc" in data["change_profile"]:
                transaction.max_soc = data["change_profile"]["max_soc"]
            
            if "min_soc" in data["change_profile"]:
                transaction.min_soc = data["change_profile"]["min_soc"]
            
            if "power" in data["change_profile"]:
                await transaction.set_power(data["change_profile"]["power"])



async def get_input(cp):
    
    command_map={
        "trans":cp.make_transaction,
        "start":cp.random_simulation,
    }

    while True:
        command = await ainput("")
        if command in command_map:
            await command_map[command]()


async def main(p, f, cp_id="CP_1"):

    logging.info("Trying to connect to csms with id %s", cp_id)

    async with websockets.connect(
        'ws://{cp_id}:{password}@localhost:9000/{cp_id}'.format(cp_id = cp_id, password='passcp1'),
        
            subprotocols=['ocpp2.0.1']
    ) as ws:

        cp = ChargePoint(cp_id, ws, p, f)

        #shut down handler
        signal.signal(signal.SIGINT, cp.shut_down)

        await asyncio.gather(cp.start(), cp.cold_Boot(), cp.wait_shut_down())



if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("-p", type=int, default = 5*60, help="event_period_time")
    parser.add_argument("-f", type=str, default = 60, help="factor")
    args = parser.parse_args()    

    asyncio.run(main(args.p, args.f))