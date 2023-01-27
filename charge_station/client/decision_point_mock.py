import logging
import asyncio
import websockets
from os import path
import sys
from datetime import datetime

sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
from fanout_Rabbit_Handler import Fanout_Rabbit_Handler, Fanout_Message
from ocpp.v201 import call
from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call, call_result, enums, datatypes
logging.basicConfig(level=logging.INFO)


async def handle_requet(request):
    if "request_" not in request.intent:
        return request.content


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

    await broker.send_request_wait_response(message)

    ########
    input()

    message = Fanout_Message(
        intent="request_authorize",
        type="REQUEST",
        content=call.AuthorizePayload(
            id_token=datatypes.IdTokenType(id_token = "123456789", type=enums.IdTokenType.iso14443)
        )
    )
    await broker.send_request_wait_response(message)

    ########
    input()
    message = Fanout_Message(
        intent="request_status_notification",
        type="REQUEST",
        content=call.StatusNotificationPayload(
            timestamp=datetime.utcnow().isoformat(),
            evse_id=1,
            connector_id=1,
            connector_status=enums.ConnectorStatusType.occupied
        )
    )
    await broker.send_request_wait_response(message)

    message = Fanout_Message(
        intent="request_transaction_event",
        type="REQUEST",
        content=call.TransactionEventPayload(
            event_type=enums.TransactionEventType.started,
            timestamp=datetime.utcnow().isoformat(),
            trigger_reason=enums.TriggerReasonType.ev_detected,
            seq_no=1,
            transaction_info=datatypes.TransactionType(transaction_id="jkhsdalkvsdj"),
            evse=datatypes.EVSEType(id=1)
        )
    )
    await broker.send_request_wait_response(message)



if __name__ == '__main__':
   asyncio.run(main())

