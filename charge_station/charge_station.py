import logging
import asyncio
import websockets
from ocpp.v201 import call
from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call, call_result, enums, datatypes
import sys
logging.basicConfig(level=logging.INFO)


class ChargePoint(cp):

    async def send_boot_notification(self):
        request = call.BootNotificationPayload(
            charging_station={
                'model': 'Wallbox XYZ',
                'vendor_name': 'anewone'
            },
            reason="PowerUp"
        )
        response = await self.call(request)

        if response.status == enums.RegistrationStatusType.accepted:
            print("Connected to central system.")



async def main(cp_id):

    logging.info("Trying to connect to csms with id %s", cp_id)

    async with websockets.connect(
        'ws://{cp_id}:{password}@localhost:9000/{cp_id}'.format(cp_id = cp_id, password='passcp1'),
        
            subprotocols=['ocpp2.0.1']
    ) as ws:

        cp = ChargePoint(cp_id, ws)

        await asyncio.gather(cp.start())


if __name__ == '__main__':
   asyncio.run(main(sys.argv[1]))