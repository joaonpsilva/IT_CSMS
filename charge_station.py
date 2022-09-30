import asyncio
import logging
import websockets
from ocpp.routing import after,on
import sys

from ocpp.v201 import call
from ocpp.v201 import ChargePoint as cp

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

       if response.status == 'Accepted':
           print("Connected to central system.")


async def main(id):

    cp_id = "CP_" + id
    async with websockets.connect(
        'ws://localhost:9000/' + cp_id,
        
            subprotocols=['ocpp2.0.1']
    ) as ws:

        cp = ChargePoint(cp_id, ws)

        await asyncio.gather(cp.start(), cp.send_boot_notification())


if __name__ == '__main__':
   asyncio.run(main(sys.argv[1]))