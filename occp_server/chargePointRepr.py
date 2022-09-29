from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call_result

from ocpp.routing import on
from datetime import datetime


class ChargePoint(cp):
    @on('BootNotification')
    async def on_boot_notification(self, charging_station, reason, **kwargs):
        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status='Accepted'
        )