import logging
import asyncio
import websockets
from datetime import datetime
import argparse
import sys

from rabbit_mq.fanout_Rabbit_Handler import Fanout_Rabbit_Handler, Fanout_Message

from db.db_CS import DataBase_CP
from ocpp.v201 import call
from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call, call_result, enums, datatypes
from ocpp.routing import after,on
from ocpp import exceptions
import traceback
logging.basicConfig(level=logging.INFO)
logging.getLogger("websockets").setLevel(logging.CRITICAL)
from charge_station.client.Transaction import Transaction

import signal


class ChargePoint(cp):

    def __init__(self, cp_id, ws=None):
        super().__init__(cp_id, ws)

        self.status = None
        self.db = DataBase_CP()
        self.connection_active = False

        self.ongoing_transactions = {}
        self.known_evses = {}
        self.queued_messages = []
        self.trigger_messages = []

    
    def shut_down(self, sig, frame):
        self.db.store_Queued_Messages(self.queued_messages)

        logging.info("Shuting down")
        sys.exit(0)


    async def _handle_call(self, msg):
        try:
            handlers = self.route_map[msg.action]
            
            #B03.FR.08
            if self.status == enums.RegistrationStatusType.rejected:
                if not (handlers['_on_action'] == self.on_TriggerMessage and \
                msg.payload["requestedMessage"] == enums.MessageTriggerType.boot_notification):
                    response = msg.create_call_error(exceptions.SecurityError).to_json()
                    await self._send(response)
                    return
            
            #B02.FR.01 B02.FR.02, Should return security error?
            elif self.status == enums.RegistrationStatusType.pending:
                if handlers['_on_action'] not in [self.on_set_variables, self.on_get_variables,
                    self.on_GetBaseReport, self.on_GetReport, self.on_TriggerMessage]:
                    response = msg.create_call_error(exceptions.SecurityError).to_json()
                    await self._send(response)
                    return


        except KeyError:
            pass
        
        return await super()._handle_call(msg)


    async def call(self, payload, suppress=True):

        if not self.connection_active:
            raise ConnectionError
        
        if not isinstance(payload, call.BootNotificationPayload):
            if self.status is None or self.status == enums.RegistrationStatusType.rejected:
                raise PermissionError

            if self.status == enums.RegistrationStatusType.pending:
                #verify if messages can be sent B02.FR.02
                if not isinstance(payload, call.NotifyReportPayload):
                    raise PermissionError
                #message was triggered    
                if not payload.__class__.__name__[:-7] in self.trigger_messages: #remove "Payload"
                    raise PermissionError
                else:
                    self.trigger_messages.remove(payload.__class__.__name__[:-7])

        return await super().call(payload, suppress)


    async def run(self, rabbit, server_port, password):

        #broker handles the rabbit mq queues and communication between services
        self.broker = Fanout_Rabbit_Handler("OCPPclient", self.handle_request)
        await self.broker.connect(rabbit)

        self.queued_messages = self.db.get_Queued_Messages()
        
        #Connect to server CSMS        
        async for websocket in websockets.connect(
        'ws://{cp_id}:{password}@localhost:{server_port}/{cp_id}'.format(cp_id = self.id, password=password, server_port=server_port),
            subprotocols=['ocpp2.0.1']
        ):
            try:
                logging.info("Connection established with CSMS")

                self._connection = websocket
                self.connection_active = True

                await self.start()

            except websockets.ConnectionClosed:
                self.connection_active = False
                logging.info("Connection Error. Trying to restore connection")
                continue
        
       
    async def handle_request(self, request):
        """
        CallBack function that is called when a request is received on RabbitMq
        """

        try:
            #Check if method requested is implemented
            method = getattr(self, request.intent)
        except:
            #Ignore the request
            return 

        try:
            return await method(**request.content)
        except:
            logging.error(traceback.format_exc())

            
    async def send_queued_messages(self):
        """
        Function to be called once connection is established
        Sends all messages stored in message queue
        """

        logging.info("Checking for Queued Messages to Send")

        #While there are still queued messages
        while len(self.queued_messages) > 0:
            if not self.connection_active:
                break
            
            #pick a message and try to send it
            message = self.queued_messages[0]
            try:
                await self.call(message)
                self.queued_messages.pop(0)
            except:
                logging.error(traceback.format_exc())
        
        logging.info("No more Queued Messages")

            
    async def request_transaction_event(self, **kwargs):
        """Handle TransactionEvent from RabbitMq"""
        #TODO REVIEW authorization

        request = call.TransactionEventPayload(**kwargs)

        #new transaction
        transaction_id = request.transaction_info["transaction_id"]
        if transaction_id not in self.ongoing_transactions:
            transaction = Transaction(transaction_id)
            self.ongoing_transactions[transaction_id] = transaction
        else:
            transaction = self.ongoing_transactions[transaction_id]

        #user localy stops transaction 
        if request.id_token is not None and request.transaction_info["stopped_reason"] in [None, enums.ReasonType.local]:
            #check if idtoken can stop transaction

            if not transaction.check_valid_stop_with_Idtoken(request.id_token): #id token is not the same
                
                #get info from token (1st from db then from CSMS)
                auth_response = await self.request_authorize({"id_token": request.id_token})

                if not transaction.check_valid_stop_with_GroupIdtoken(auth_response.id_token_info): #Compare groupIdToken
                    #Not authorized to stop transaction
                    return {"id_token_info":{"status":enums.AuthorizationStatusType.invalid}}
        
        if request.evse is not None:
            #Save information regarding evse
            transaction.evseId = request.evse["id"]
            transaction.connectorId = request.evse["connector_id"] if "connector_id" in request.evse else None

            #add transaction to evse dict
            self.known_evses[request.evse["id"]]["transaction"] = transaction
        

        if request.event_type == enums.TransactionEventType.ended:
            #delete from ongoing trans
            self.ongoing_transactions.pop(transaction_id)

            #delete from evse map
            evseId = transaction.evseId
            self.known_evses[evseId]["transaction"] = None

        #Try to send event to the CSMS
        try:
            assert(self.connection_active)
            assert(self.status == enums.RegistrationStatusType.accepted)
            response = await self.call(request)
        except:
            #Store request in message queue that will be sent once connection is restored
            request.offline = True
            self.queued_messages.append(request)
            response = call_result.TransactionEventPayload()
        
        if request.id_token is not None and response.id_token_info["status"] == enums.AuthorizationStatusType.accepted:
            transaction.authorized = True
            transaction.start_idToken = request.id_token
            transaction.group_idToken = response.id_token_info["group_id_token"]

        return response

    
    async def request_boot_notification(self, **kwargs):
        """Handle BootNotification from RabbitMq"""

        request = call.BootNotificationPayload(**kwargs)

        try:
            response = await self.call(request)
        except:
            response = call_result.BootNotificationPayload(status=enums.RegistrationStatusType.rejected)

        loop = asyncio.get_event_loop()
        self.status = response.status

        if response.status == enums.RegistrationStatusType.accepted:
            #initiate heart beat?
            loop.create_task(self.heartBeat(response.interval))

            #send queued message when connection is restored
            await self.send_queued_messages()

        else:
            #Retry boot after x senconds
            loop.call_later(response.interval, loop.create_task, self.request_boot_notification(**kwargs))
        
        return response
        
  
    async def heartBeat(self, interval):
        while True:
            request = call.HeartbeatPayload()
            response = await self.call(request)
            await asyncio.sleep(interval)
    

    async def authorize_with_localList(self, id_token):
        """
        Authorize IdToken using local authorization list

        returns idTokenInfo
        """

        #no authorization
        if id_token["type"] == enums.IdTokenType.no_authorization:
            return {"status": enums.AuthorizationStatusType.accepted}

        #get idtoken info from db
        try:
            response = self.db.get_IdToken_Info(id_token)
            id_token =response["id_token"]
            id_token_info =response["id_token_info"]
            if id_token is None:
                return {"status" : enums.AuthorizationStatusType.unknown}

            #assert its the same idtoken
            assert(id_token["id_token"] == id_token["id_token"])
            assert(id_token["type"] == id_token["type"])

            #If id token is valid and known, check status
            id_token_info["status"] =  enums.AuthorizationStatusType.accepted

            #expired
            if id_token_info["cache_expiry_date_time"] != None and id_token_info["cache_expiry_date_time"] < datetime.utcnow().isoformat():
                id_token_info["status"] = enums.AuthorizationStatusType.expired

        except:
            logging.error(traceback.format_exc())
            id_token_info = {"status": enums.AuthorizationStatusType.invalid}
        
        return id_token_info
        
    
    async def request_authorize(self, **kwargs):
        """
        Authorize IdToken
        Tries to authorize with local list first
        If failed, send AuthorizeRequest to the CSMS
        """

        id_token_info = await self.authorize_with_localList(kwargs["id_token"])
        auth_response = call_result.AuthorizePayload(id_token_info=id_token_info)

        logging.info("Local Auth result: %s", id_token_info["status"])

        if id_token_info["status"] != enums.AuthorizationStatusType.accepted and self.connection_active:
            #Ask the CSMS
            request = call.AuthorizePayload(**kwargs)
            auth_response = await self.call(request)
        
        return auth_response
    

    async def request_meter_values(self, **kwargs):
        request = call.MeterValuesPayload(**kwargs)
        return await self.call(request)
    

    async def request_status_notification(self, **kwargs):
        evse = kwargs["evse_id"]
        connector = kwargs["connector_id"]

        if evse not in self.known_evses:
            self.known_evses[evse] = {"connectors":set(), "transaction":None}

        if connector not in self.known_evses[evse]["connectors"]:
            self.known_evses[evse]["connectors"].add(connector)


        request = call.StatusNotificationPayload(**kwargs)
        return await self.call(request)

    #---------------------------------------------------------------------------------
    
    @on('TriggerMessage')
    async def on_TriggerMessage(self, **kwargs):
        
        try:
            #Forward message to RabbitMq
            #If no response, reject the request

            message = Fanout_Message(intent="trigger_message", content=kwargs)
            response = await self.broker.send_request_wait_response(message)

            if response["status"] == enums.TriggerMessageStatusType.accepted:
                self.trigger_messages.append(kwargs["requested_message"])
            
            response = call_result.TriggerMessagePayload(**response)
        
        except TimeoutError:
            response = call_result.TriggerMessagePayload(status=enums.TriggerMessageStatusType.rejected)

        return response


    @on('RequestStartTransaction')
    async def on_RequestStartTransaction(self, **kwargs):

        try:
            #B02.FR.05
            assert(self.status == enums.RegistrationStatusType.accepted)

            #Send message to decision Point
            message = Fanout_Message(intent="remote_start_transaction", content=kwargs)
            response = await self.broker.send_request_wait_response(message)
            response = call_result.RequestStartTransactionPayload(**response)
        
        except (AssertionError,TimeoutError) :
            response = call_result.RequestStartTransactionPayload(status=enums.RequestStartStopStatusType.rejected)
        
        #If transaction already occuring return transaction ID
        try:
            if response.transaction_id is None:
                response.transaction_id = self.known_evses[kwargs["evse_id"]]["transaction"].transaction_id
        except:
            pass
        
        return response
    

    @on('RequestStopTransaction')
    async def on_RequestStopTransaction(self, **kwargs):

        try:
            #F03.FR.08
            assert(kwargs["transaction_id"] in self.ongoing_transactions)

            message = Fanout_Message(intent="remote_stop_transaction", content=kwargs)
            response = await self.broker.send_request_wait_response(message)
            response = call_result.RequestStopTransactionPayload(**response)

        except (AssertionError,TimeoutError):
            response = call_result.RequestStopTransactionPayload(status=enums.RequestStartStopStatusType.rejected)

        return response

    
    @on("UnlockConnector")
    async def on_UnlockConnector(self, **kwargs):
        #F05.FR.03
        if kwargs["evse_id"] not in self.known_evses or kwargs["connector_id"] not in self.known_evses[kwargs["evse_id"]]["connectors"]:
            return call_result.UnlockConnectorPayload(status=enums.UnlockStatusType.unknown_connector)

        #F05.FR.02
        transaction = self.known_evses[kwargs["evse_id"]]["transaction"]
        if transaction and transaction.connectorId == kwargs["connector_id"] and transaction.authorized:
            return call_result.UnlockConnectorPayload(status=enums.UnlockStatusType.ongoing_authorized_transaction)

        try:
            message = Fanout_Message(intent="unlock_connector", content=kwargs)
            response = await self.broker.send_request_wait_response(message)
            response = call_result.UnlockConnectorPayload(**response)
            
        except TimeoutError:
            response = call_result.UnlockConnectorPayload(status=enums.UnlockStatusType.unlock_failed)
            
        return response
    
    
    @on("Reset")
    async def on_Reset(self, **kwargs):

        try:
            message = Fanout_Message(intent="reset", content=kwargs)
            response = await self.broker.send_request_wait_response(message)
            response =  call_result.ResetPayload(**response)
        except TimeoutError:
            response = call_result.ResetPayload(status=enums.ResetStatusType.rejected)
            
        return response
    

    @on("ChangeAvailability")
    async def on_ChangeAvailability(self, **kwargs):

        try:
            message = Fanout_Message(intent="change_availability", content=kwargs)
            response = await self.broker.send_request_wait_response(message)
            response = call_result.ChangeAvailabilityPayload(**response)
        except TimeoutError:
            response = call_result.ChangeAvailabilityPayload(status=enums.ChangeAvailabilityStatusType.rejected)
            
        return response
    

    @on("SetChargingProfile")
    async def on_SetChargingProfile(self,**kwargs):
        try:
            message = Fanout_Message(intent="set_charging_profile", content=kwargs)
            response = await self.broker.send_request_wait_response(message)
            response = call_result.SetChargingProfilePayload(**response)
        except TimeoutError:
            response = call_result.SetChargingProfilePayload(status=enums.ChargingProfileStatus.rejected)

        return response


    @on("GetCompositeSchedule")
    async def on_GetCompositeSchedule(self, **kwargs):
        try:
            message = Fanout_Message(intent="get_composite_schedule", content=kwargs)
            response = await self.broker.send_request_wait_response(message)
            response = call_result.GetCompositeSchedulePayload(**response)
        except TimeoutError:
            response = call_result.GetCompositeSchedulePayload(status=enums.GenericStatusType.rejected)

        return response


    @on("ClearChargingProfile")
    async def on_ClearChargingProfileRequest(self, **kwargs):
        try:
            message = Fanout_Message(intent="clear_charging_profile", content=kwargs)
            response = await self.broker.send_request_wait_response(message)
            response = call_result.ClearChargingProfilePayload(**response)
        except TimeoutError:
            response = call_result.ClearChargingProfilePayload(status=enums.ClearChargingProfileStatusType.unknown)

        return response
    
    @on("GetChargingProfiles")
    async def on_GetChargingProfiles(self, **kwargs):
        try:
            message = Fanout_Message(intent="get_charging_profiles", content=kwargs)
            response = await self.broker.send_request_wait_response(message)
            response = call_result.GetChargingProfilesPayload(**response)
        except TimeoutError:
            response = call_result.GetChargingProfilesPayload(status=enums.GenericStatusType.rejected)

        return response
    

    @on("GetLocalListVersion")
    async def on_GetLocalListVersion(self):
        try:
            version = self.db.get_LocalList_Version()
        except:
            version = 0
        return call_result.GetLocalListVersionPayload(version_number=version)
    
    @on("SendLocalList")
    async def on_SendLocalList(self, **kwargs):

        current_version = self.db.get_LocalList_Version()
        if 0 >= kwargs["version_number"] <= current_version:
            status = enums.SendLocalListStatusType.version_mismatch
        else:
            resulted = self.db.updateLocalList(**kwargs)
            if resulted:
                status = enums.SendLocalListStatusType.accepted
            else:
                status = enums.SendLocalListStatusType.failed

        return call_result.SendLocalListPayload(status=status)
    
    
    @on('GetVariables')
    def on_get_variables(self,get_variable_data,**kwargs):

        get_variable_result=[]
        
        for variable_data in get_variable_data:
            status, value = self.db.getVariable(**variable_data)

            get_variable_result.append(
                datatypes.GetVariableResultType(
                    attribute_status= status, 
                    component=variable_data["component"],
                    variable= variable_data["variable"],
                    attribute_value=value
                )   
            )
            
        return call_result.GetVariablesPayload(get_variable_result=get_variable_result)
    

    @on('SetVariables')
    def on_set_variables(self, set_variable_data):
        set_variable_result=[]

        for variable_data in set_variable_data:
            try:
                status = self.db.setVariable(**variable_data)
            except:
                status = enums.SetVariableStatusType.rejected

            set_variable_result.append(
                datatypes.SetVariableResultType(
                    attribute_status= status, 
                    component=variable_data["component"],
                    variable= variable_data["variable"]
                )   
            )
            
        return call_result.SetVariablesPayload(set_variable_result=set_variable_result)
    

    @on('GetTransactionStatus')
    def on_GetTransactionStatus(self, transaction_id):

        on_going = transaction_id in self.ongoing_transactions
        
        messages_in_queue = False
        for message in self.queued_messages:
            if isinstance(message, call.TransactionEventPayload):
                if message.transaction_info["transaction_id"] == transaction_id:
                    messages_in_queue = True
                    break
        
        return call_result.GetTransactionStatusPayload(messages_in_queue=messages_in_queue, ongoing_indicator=on_going)
    

    @on("GetBaseReport")
    async def on_GetBaseReport(self, **kwargs):
        try:
            message = Fanout_Message(intent="get_base_report", content=kwargs)
            response = await self.broker.send_request_wait_response(message)
            response = call_result.GetBaseReportPayload(**response)
        except TimeoutError:
            response = call_result.GetBaseReportPayload(status=enums.GenericDeviceModelStatusType.rejected)

        return response
    

    @on("ReserveNow")
    async def on_ReserveNow(self, **kwargs):
        try:
            status, value = self.db.getVariable({"name":"ReservationCtrlr"}, {"name":"Available"})
            if status == enums.GetVariableStatusType.accepted:
                if value != "True":
                    logging.info("CP not accepting reservations")
                    raise ValueError

            message = Fanout_Message(intent="get_base_report", content=kwargs)
            response = await self.broker.send_request_wait_response(message, timeout=2)
            response = call_result.ReserveNowPayload(**response)

        except (TimeoutError, ValueError):
            response = call_result.ReserveNowPayload(status=enums.ReserveNowStatusType.rejected)

        return response

    @on("CancelReservation")
    def on_CancelReservation(self, **kwargs):
        pass
    
    @on("SetVariableMonitoring")
    async def on_SetVariableMonitoring(self, set_monitoring_data, **kwargs):
        pass
    
    @on("ClearVariableMonitoring")
    async def on_ClearVariableMonitoring(self, id, **kwargs):
        pass
    
    

async def main(args):
    cp = ChargePoint(args.cp)

    #shut down handler
    signal.signal(signal.SIGINT, cp.shut_down)

    await cp.run(args.rb, args.p, args.pw)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", type=int, default = 9000, help="OCPP server port")
    parser.add_argument("-rb", type=str, default = "amqp://guest:guest@localhost/", help="RabbitMq")
    parser.add_argument("-cp", type=str, default = "CP_1", help="Cp_id")
    parser.add_argument("-pw", type=str, default = "passcp1", help="Cp password")
    args = parser.parse_args()

    asyncio.run(main(args))