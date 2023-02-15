#!/bin/bash
cd src

python3 -m CSMS.api.api &
python3 -m CSMS.ocpp_server.ocpp_server &
python3 -m CSMS.db.db &


echo "Press 'q' to exit"
while : ; do
read -n 1 k <&1
if [[ $k = q ]] ; then
kill $(pgrep -f 'python3 -m CSMS.db.db')
kill $(pgrep -f 'python3 -m CSMS.ocpp_server.ocpp_server')
kill $(pgrep -f 'python3 -m CSMS.api.api')
break
fi
done

sleep 1



