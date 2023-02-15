import subprocess
import signal
import sys
import time

api = subprocess.Popen(["python3", "-m", "CSMS.api.api"])
ocpp_server = subprocess.Popen(["python3", "-m", "CSMS.ocpp_server.ocpp_server"])
db = subprocess.Popen(["python3", "-m", "CSMS.db.db"])

def terminate(sig=None, frame=None):
    api.terminate()
    ocpp_server.terminate()
    db.terminate()
    time.sleep(1)
    sys.exit(0)


#shut down handler
signal.signal(signal.SIGINT, terminate)

while True:
    user_input = input()
    if user_input == "q":
        terminate()
        

