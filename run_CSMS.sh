#!/bin/sh
python3 CSMS/api/api.py &
python3 CSMS/db/db.py &
python3 CSMS/ocpp_server/ocpp_server.py