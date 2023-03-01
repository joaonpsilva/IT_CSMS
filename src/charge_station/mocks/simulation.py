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


class ChargePoint(cp):

    def __init__(self, id, connection):
        super().__init__(id, connection)

        self.evses = {
            1: {"availale": True, "connectors" : [1,2]},
            2: {"availale": True, "connectors" : [1,2,3]},
            3: {"availale": True, "connectors" : [1,2]}
        }

        self.active_transactions = {}
        

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
    


    async def make_transaction(self):

        available_evses = [evse for evse, info in self.evses.items() if info["availale"]]

        if len(available_evses) == 0:
            logging.info("There are no free evses")
            return
        
        evse_id = random.choice(available_evses)
        connector_id = random.choice(self.evses[evse_id]["connectors"])
        self.evses[evse_id]["available"] = False

        transaction = Transaction(evse_id, connector_id, self.call)
        self.active_transactions[transaction.transaction_id] = transaction

        await transaction.start_event()
        await transaction.authorize_event()
        await transaction.charging_events()
        await transaction.end_event()

        self.active_transactions.pop(transaction.transaction_id)
        self.evses[evse_id]["available"] = True
    

    @on("SetChargingProfile")
    async def on_SetChargingProfile(self, evse_id, charging_profile):

        charging_profile = datatypes.ChargingProfileType(**charging_profile)

        if charging_profile.transaction_id is not None:
            self.active_transactions[charging_profile.transaction_id].new_charge_values.set_result("XXXXXXXX")

        return call_result.SetChargingProfilePayload(status=enums.ChargingProfileStatus.accepted)

    @on("GetChargingProfiles")
    async def on_GetChargingProfiles(self, request_id, charging_profile, **kwargs):
        return call_result.GetChargingProfilesPayload(status=enums.GetChargingProfileStatusType.no_profiles)



async def get_input(cp):
    
    command_map={
        "start":cp.make_transaction,
    }

    while True:
        command = await ainput("")
        if command in command_map:
            await command_map[command]()


async def main(cp_id="CP_1"):

    logging.info("Trying to connect to csms with id %s", cp_id)

    async with websockets.connect(
        'ws://{cp_id}:{password}@localhost:9000/{cp_id}'.format(cp_id = cp_id, password='passcp1'),
        
            subprotocols=['ocpp2.0.1']
    ) as ws:

        cp = ChargePoint(cp_id, ws)
        await asyncio.gather(cp.start(), cp.cold_Boot(), get_input(cp))



if __name__ == '__main__':
   asyncio.run(main())