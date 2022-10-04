from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call, call_result, enums, datatypes

from ocpp.routing import on
from datetime import datetime

import logging

logging.basicConfig(level=logging.INFO)


class ChargePoint(cp):

    def __init__(self, id, connection, response_timeout=30):
        super().__init__(id, connection, response_timeout)

        self.method_mapping = {
            "GETVARIABLES" : self.getVariables
        }
    
    async def send_CP_Message(self, method, payload):
        return await self.method_mapping[method](payload)
        
    
    @on('BootNotification')
    async def on_boot_notification(self, charging_station, reason, **kwargs):

        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status='Accepted'
        )


    async def getVariables(self, payload):

        request = call.GetVariablesPayload(get_variable_data=payload)

        return await self.call(request)
    
 