import json
import logging

from fastapi import FastAPI, WebSocket
from starlette.responses import FileResponse 

from dse import DSESimulator


# Load default registers
with open('dse_registers.json', 'r') as f:
    registers = json.load(f)

# Load default alarms
with open('dse_alarms.json', 'r') as f:
    alarms = json.load(f)

simulator = DSESimulator(
    host='0.0.0.0', 
    port=502, 
    registers=registers, 
    alarms=alarms,
    no_block=True
)

simulator.set_register('/AutoStart', 1)
simulator.start()



app = FastAPI()

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
        
        logging.info(data['msg'])
        
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
