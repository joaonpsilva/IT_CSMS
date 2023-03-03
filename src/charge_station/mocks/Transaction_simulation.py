import random
import uuid
from ocpp.v201 import call, call_result, enums, datatypes
from datetime import datetime
import logging
import asyncio
import time

class Transaction:

    def __init__(self, evse_id, connector_id, call, event_period_time=5*60, factor=60) -> None:
        self.call = call

        self.loop = asyncio.get_running_loop()
        self.periodic_meter = None
        self.last_meter_values_time = None

        self.event_period_time=event_period_time
        self.factor = factor

        self._transaction_seq_no = 0

        self.evse_id = evse_id
        self.connector_id = connector_id
        self.transaction_id = str(uuid.uuid4())

        self.ev_total_capacity = random.choice([20000,24000,40000])
        self.soc = min(max(random.gauss(50, 20), 5), 95)
        self.ev_current_capacity = self.soc/100 * self.ev_total_capacity

        self.time_charging_goal = random.randrange(30*60, 60*60*12)
        self._time_current = 0
        self.done_charging = asyncio.Event()

        self._power = 0
        self.total_import = 0
        self.total_export = 0

        self._charging_action = None
        self.max_soc = None
        self.min_soc = None

        logging.info(
            "Starting transaction\n \
            EVSE: {evse} \n\
            connector_id: {connector_id} \n\
            transaction_id: {transaction_id} \n\
            ev_total_capacity: {ev_total_capacity} \n\
            time_charging_goal: {time_charging_goal}\
            ".format(evse=self.evse_id,
                     connector_id=self.connector_id,
                     transaction_id=self.transaction_id,
                     ev_total_capacity=self.ev_total_capacity,
                     time_charging_goal=self.time_charging_goal,
                     )
        )
    
    @property
    def transaction_seq_no(self):
        self._transaction_seq_no+=1
        return self._transaction_seq_no - 1 
    
    @property
    def charging_action(self):
        return self._charging_action

    @property
    def time_current(self):
        return self._time_current


    @property
    def power(self):
        return self._power

    @power.setter
    async def power(self, p):
        self._power = p

        if self.charging_action == 3:
            self.current_import = power
        elif self.charging_action == 4:
            self.current_export = power
        
        enums.TriggerReasonType.charging_rate_changed


    @time_current.setter
    def time_current(self, t):
        self._time_current = t

        #enough time has passed
        if self._time_current >= self.time_charging_goal:
            self.done_charging.set()


    @charging_action.setter
    def charging_action(self, action):
        self._charging_action = action

        if self._charging_action == 2:
            self.power = 0

    

    async def status_notif(self, connector_status):
        #STATUS NOTIF
        request = call.StatusNotificationPayload(
            timestamp=datetime.utcnow().isoformat(),
            connector_status=connector_status,
            evse_id=self.evse_id,
            connector_id=self.connector_id
        )
        await self.call(request)
    
    
    async def start_event(self):
        #START EVENT

        await self.status_notif(enums.ConnectorStatusType.occupied)

        request = call.TransactionEventPayload(
            event_type=enums.TransactionEventType.started,
            timestamp=datetime.utcnow().isoformat(),
            trigger_reason=enums.TriggerReasonType.cable_plugged_in,
            seq_no=self.transaction_seq_no,
            transaction_info=datatypes.TransactionType(
                transaction_id=self.transaction_id,
                charging_state=enums.ChargingStateType.ev_connected
            ),
            evse=datatypes.EVSEType(id=self.evse_id, connector_id=self.connector_id),
            meter_value=self.build_meter_values(0, 0, 0, 0, self.soc)
        )
        await self.call(request)
    

    async def end_event(self):
        #END EVENT
        request = call.TransactionEventPayload(
            event_type=enums.TransactionEventType.ended,
            timestamp=datetime.utcnow().isoformat(),
            trigger_reason=enums.TriggerReasonType.ev_departed,
            seq_no=self.transaction_seq_no,
            transaction_info=datatypes.TransactionType(
                transaction_id=self.transaction_id,
                charging_state=enums.ChargingStateType.idle
            ),
            meter_value=self.build_meter_values(self.total_export, self.total_import, 0, 0, self.soc)
        )
        await self.call(request)

        await self.status_notif(enums.ConnectorStatusType.available)
    

    async def authorizeRequest(self):
        request = call.AuthorizePayload(
            id_token=datatypes.IdTokenType(
                id_token="3e19b1cc-7858-440c-bd7f-7335555841bd",
                type=enums.IdTokenType.local
            )
        )
        response = await self.call(request)
        return response.id_token_info['status'] == "Accepted"
    

    async def authorize_event(self):
        if await self.authorizeRequest():
                logging.info("User authorization successful")
        else:
            logging.info("User authorization unsuccessful")
            return 
        
        request = call.TransactionEventPayload(
            event_type=enums.TransactionEventType.updated,
            timestamp=datetime.utcnow().isoformat(),
            trigger_reason=enums.TriggerReasonType.authorized,
            seq_no=self.transaction_seq_no,
            transaction_info=datatypes.TransactionType(
                transaction_id=self.transaction_id,
                charging_state=enums.ChargingStateType.idle
            ),
            id_token=datatypes.IdTokenType(
                id_token="3e19b1cc-7858-440c-bd7f-7335555841bd",
                type=enums.IdTokenType.local
            ),
            evse=datatypes.EVSEType(id=self.evse_id, connector_id=self.connector_id),
            meter_value=self.build_meter_values(0, 0, 0, 0, self.soc)
        )
        await self.call(request)
    

    def build_meter_values(self, export_register, import_register, active_export, active_import, soc):
        meter_value=[
            datatypes.MeterValueType(
                timestamp=datetime.utcnow().isoformat(),
                sampled_value=[
                    datatypes.SampledValueType(
                        value=export_register,
                        measurand=enums.MeasurandType.energy_active_export_register
                    ),
                    datatypes.SampledValueType(
                        value=import_register,
                        measurand=enums.MeasurandType.energy_active_import_register
                    ),
                    datatypes.SampledValueType(
                        value=active_export,
                        measurand=enums.MeasurandType.power_active_export
                    ),
                    datatypes.SampledValueType(
                        value=active_import,
                        measurand=enums.MeasurandType.power_active_import
                    ),
                    datatypes.SampledValueType(
                        value=soc,
                        measurand=enums.MeasurandType.soc
                    )])]

        return meter_value
    

    def update_charging_variables(self):

        time_since_update = (time.time() - self.last_meter_values_time) * self.factor
        self.time_current = self.time_current + time_since_update

        #w to wh
        amount_exported = self.current_export * time_since_update/60/60
        amount_imported = self.current_import * time_since_update/60/60

        self.total_export += amount_exported
        self.total_import += amount_imported
        
        self.ev_current_capacity = self.ev_current_capacity + amount_imported - amount_exported 
        self.soc = self.ev_current_capacity / self.ev_total_capacity * 100
    

    async def send_update_Transaction_Event(self, trigger_reason):
        self.update_charging_variables()

        request = call.TransactionEventPayload(
            event_type=enums.TransactionEventType.updated,
            timestamp=datetime.utcnow().isoformat(),
            trigger_reason=trigger_reason,
            seq_no=self.transaction_seq_no,
            transaction_info=datatypes.TransactionType(
                transaction_id=self.transaction_id,
                charging_state=enums.ChargingStateType.charging
            ),
            evse=datatypes.EVSEType(id=self.evse_id, connector_id=self.connector_id),
            meter_value=self.build_meter_values(self.total_export, self.total_import, self.current_export, self.current_import, self.soc)
        )
        await self.call(request)
        self.last_meter_values_time = time.time()


    async def charging_events(self):

        
        self.last_meter_values_time = time.time()

        #start periodic meter values
        self.periodic_meter = self.loop.call_later(self.event_period_time/self.factor, self.loop.create_task, self.periodic_meter_values())

        #wait csms corrections until end of transaction
        await self.done_charging.wait()
     
        await self.send_update_Transaction_Event(enums.TriggerReasonType.charging_rate_changed)


        self.periodic_meter.cancel()
        

    async def periodic_meter_values(self):
        await self.send_update_Transaction_Event(enums.TriggerReasonType.meter_value_periodic)
        self.periodic_meter = self.loop.call_later(self.event_period_time/self.factor, self.loop.create_task, self.periodic_meter_values())