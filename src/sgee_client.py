from sseclient import SSEClient
import requests
import asyncio
import json

def run_decision_algorithm():
    print("Running Decision Algorithm")


def listen_stream(token):
    url="http://localhost:8000/stream"
    params={"events" : "TransactionEvent"}

    stream_response = requests.get(url, params=params, stream=True, headers={"Authorization": "Bearer " + token})

    client = SSEClient(stream_response)
    for msg in client.events():
        
        try:
            data = json.loads(msg.data)
        except:
            continue 

        if data["event_type"] == "Started":
            print("New transaction Started")
            run_decision_algorithm()


async def run_periodicly():
    while True:
        run_decision_algorithm()
        await asyncio.sleep(5)


async def main():
    params = {"email" : "admin", "password" : "admin"}
    login = requests.get("http://localhost:8000/login", params=params)
    token = login.json()["token"]

    loop = asyncio.get_event_loop()

    asyncio.create_task(run_periodicly())
    await loop.run_in_executor(None, listen_stream, token)    


if __name__ == '__main__':
    asyncio.run(main())
