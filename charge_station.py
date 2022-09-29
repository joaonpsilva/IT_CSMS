import asyncio
import logging
import websockets
from ocpp.routing import after,on

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


async def main():
   async with websockets.connect(
       'ws://localhost:9000/CP_1',
        subprotocols=['ocpp2.0.1']
   ) as ws:

       cp = ChargePoint('CP_1', ws)

       await asyncio.gather(cp.start(), cp.send_boot_notification())


if __name__ == '__main__':
   asyncio.run(main())