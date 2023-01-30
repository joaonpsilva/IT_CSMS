#!/bin/bash
python3 CSMS/api/api.py &
python3 CSMS/ocpp_server/ocpp_server.py &
python3 CSMS/db/db.py &


echo "Press 'q' to exit"
while : ; do
read -n 1 k <&1
if [[ $k = q ]] ; then
kill $(pgrep -f 'python3 CSMS/db/db.py')
kill $(pgrep -f 'python3 CSMS/ocpp_server/ocpp_server.py')
kill $(pgrep -f 'python3 CSMS/api/api.py')
break
fi
done



