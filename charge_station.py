import asyncio
import logging
import websockets
from ocpp.routing import after,on
import sys
from datetime import datetime

from ocpp.v201 import call, call_result, enums, datatypes
from ocpp.v201 import ChargePoint as cp

logging.basicConfig(level=logging.INFO)


class ChargePoint(cp):

    async def send_boot_notification(self):
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
    
    async def meterValuesRequest(self):

        meter_Values=[
            datatypes.MeterValueType(
                timestamp=datetime.utcnow().isoformat(),
                sampled_value=datatypes.SampledValueType(value=0.1))
        ]

        request = call.MeterValuesPayload(
            evse_id = self.id,
            meter_value = meter_Values
        )
    
    
    @on('GetVariables')
    async def on_get_variables(self,get_variable_data,**kwargs):

        logging.info("Received getVariables")

        get_variable_result=[]

        for var in get_variable_data:
            get_variable_result.append(
                {
                    'attribute_status': enums.GetVariableStatusType.accepted, 
                    'attribute_value' : 'ATRIBUTE_VALUE',
                    'component' : {
                        'name': var.get('component').get('name')
                    },
                    'variable' : {
                        'name': var.get('variable').get('name')
                    }
                }
                        
            )

        return call_result.GetVariablesPayload(get_variable_result)


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