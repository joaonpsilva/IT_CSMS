import logging
import asyncio
import websockets
from charge_station_Rabbit_Handler import Charge_Station_Rabbit_Handler, Fanout_Message
from ocpp.v201 import call
from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call, call_result, enums, datatypes
import sys
logging.basicConfig(level=logging.INFO)


async def handle_requet(request):
    print(request)


async def main():
    broker = Charge_Station_Rabbit_Handler(handle_requet)
    await broker.connect()

    message = Fanout_Message(
        intent="request_boot_notification",
        type="REQUEST",
        content=call.BootNotificationPayload(
            charging_station={
                'model': 'Wallbox XYZ',
                'vendor_name': 'anewone'
            },
            reason="PowerUp"
        )
    )

    await broker.ocpp_log(message)



if __name__ == '__main__':
   asyncio.run(main())

