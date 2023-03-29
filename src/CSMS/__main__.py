import subprocess
import signal
import sys
import time

ocpp_server = subprocess.Popen(["python3", "-m", "CSMS.ocpp_server.ocpp_server"])
api = subprocess.Popen(["python3", "-m", "CSMS.api.api"])
db = subprocess.Popen(["python3", "-m", "CSMS.db.db"])

def terminate(sig=None, frame=None):
    api.terminate()
    ocpp_server.send_signal(signal.SIGINT)
    db.send_signal(signal.SIGINT)
    time.sleep(1)
    sys.exit(0)


#shut down handler
signal.signal(signal.SIGINT, terminate)

while True:
    user_input = input()
    if user_input == "q":
        terminate()
        

