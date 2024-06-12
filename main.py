#! /usr/bin/python3 -u

import os
import json
import argparse

import uvicorn
from fastapi import FastAPI, WebSocket
from starlette.responses import FileResponse 

from dse import DSESimulator


app = FastAPI()
simulator = DSESimulator()

@app.get("/")
async def read_index():
    return FileResponse('index.html')

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_json()

        if 'msg' not in data:
            continue

        if data['msg'] in ['send_registers', 'set_register']:
            if data['msg'] == 'set_register':
                simulator.set_register(data['path'], float(data['val']))
                simulator.update_regs()
            await websocket.send_text(json.dumps({ 
                'msg': 'registers data attached',
                'registers': [{'path': path, **values} for path,values in simulator.registers.items()]
            }))

        elif data['msg'] in ['send_alarms', 'set_alarm']:
            if data['msg'] == 'set_alarm':
                simulator.set_alarm(data['id'], int(data['val']))
                simulator.update_alarms()
            await websocket.send_text(json.dumps({ 
                'msg': 'alarms data attached',
                'alarms': simulator.alarms
            }))

        else:
            await websocket.send_text(json.dumps({ 
                'msg': 'unknown command'
            }))


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-d',  '--app-dir',     type=str, default=os.getcwd())
    parser.add_argument('-wh', '--web-host',    type=str, default='localhost')
    parser.add_argument('-wp', '--web-port',    type=int, default=8000)
    parser.add_argument('-mh', '--modbus-host', type=str, default='0.0.0.0')
    parser.add_argument('-mp', '--modbus-port', type=int, default=502)
    args = parser.parse_args()

    os.chdir(args.app_dir)

    simulator.prepare(registers='dse_registers.json', alarms='dse_alarms.json')
    simulator.set_register('/AutoStart', 1)
    simulator.start(host=args.modbus_host, port=args.modbus_port, no_block=True)

    uvicorn.run(app, host=args.web_host, port=args.web_port)