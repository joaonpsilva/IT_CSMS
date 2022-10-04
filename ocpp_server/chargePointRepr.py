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
        """Funtion will use the mapping defined in method_mapping to call the correct function"""
        return await self.method_mapping[method](payload)


#######################Functions starting from CSMS Initiative


    async def getVariables(self, payload):
        """Funtion initiated by the csms to get variables"""
        request = call.GetVariablesPayload(get_variable_data=payload)
        return await self.call(request)


#######################Funtions staring from the CP Initiative


    @on('BootNotification')
    async def on_BootNotification(self, charging_station, reason, **kwargs):

        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status='Accepted'
        )
    
    @on('MeterValues')
    async def on_MeterValues(self, evse_id, meter_value):
        #what TODO with parameters
        return call_result.MeterValuesPayload()
    
    @on('TransactionEvent')
    async def on_TransactionEvent(self, event_type, timestamp, trigger_reason, seq_no, transaction_info, **kwargs):
        #TODO construct better TransactionEventPayload
        return call_result.TransactionEventPayload()
    
    on('StatusNotification')
    async def on_StatusNotification(self, timestamp, connector_status, evse_id, connector_id):
        #what TODO with parameters
        return call_result.StatusNotificationPayload()



    
 