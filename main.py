#! /usr/bin/python3 -u

import os
import json
import argparse

import uvicorn
import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from dse import DSESimulator
from relay_watcher import DbusRelayWatcher


app = FastAPI()


@app.get("/")
async def read_index():
    return FileResponse('index.html')

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    simulator: DSESimulator = websocket.app.state.simulator
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

        elif data['msg'] == 'scf':
            simulator.apply_scf_command(data['cmd'])

        else:
            await websocket.send_text(json.dumps({ 
                'msg': 'unknown command'
            }))


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-d',  '--app-dir',      type=str,  default=os.getcwd())
    parser.add_argument('-wh', '--web-host',     type=str,  default='localhost')
    parser.add_argument('-wp', '--web-port',     type=int,  default=8000)
    parser.add_argument('-mh', '--modbus-host',  type=str,  default='0.0.0.0')
    parser.add_argument('-mp', '--modbus-port',  type=int,  default=502)
    parser.add_argument('-hr', '--helper-relay', default=False, action='store_true')
    args = parser.parse_args()

    os.chdir(args.app_dir)

    simulator = DSESimulator(
        telemetry_start_stop=not args.helper_relay
    )

    simulator.prepare(registers='dse_registers.json', alarms='dse_alarms.json')
    simulator.set_register('/AutoStart', 1)
    simulator.start(host=args.modbus_host, port=args.modbus_port, no_block=True)

    app.state.simulator = simulator
    app.mount("/static", StaticFiles(directory="static"), name="static")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    config = uvicorn.Config(app, host=args.web_host, port=args.web_port, loop=loop)
    server = uvicorn.Server(config)

    if args.helper_relay:
        watcher = DbusRelayWatcher(simulator)
        loop.create_task(watcher.run())

    loop.run_until_complete(server.serve())
