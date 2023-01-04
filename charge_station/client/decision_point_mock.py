import logging
import asyncio
import websockets
from os import path
import sys

sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
from fanout_Rabbit_Handler import Fanout_Rabbit_Handler, Fanout_Message
from ocpp.v201 import call
from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call, call_result, enums, datatypes
logging.basicConfig(level=logging.INFO)


async def handle_requet(request):
    print(request)


async def main():
    broker = Fanout_Rabbit_Handler("decision_point", handle_requet)
    await broker.connect("amqp://guest:guest@localhost/")

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

    ########

    message = Fanout_Message(
        intent="request_authorize",
        type="REQUEST",
        content=call.AuthorizePayload(
            id_token=datatypes.IdTokenType(id_token = "123456789", type=enums.IdTokenType.iso14443)
        )
    )

    await broker.ocpp_log(message)



if __name__ == '__main__':
   asyncio.run(main())
