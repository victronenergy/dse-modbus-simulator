#!/usr/bin/env python3

import json
import time
import random
import argparse
import logging
from enum import IntEnum
from threading import Thread
from numbers import Number

from pyModbusTCP.server import ModbusServer, DataHandler


# init logging
logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)


class DSEDataHandler(DataHandler):

    def __init__(self, scf_keys, scf_cmd_handler=None, *args, **kwargs):
        self.scf_keys = scf_keys
        self.scf_cmd_handler = scf_cmd_handler
        super(DSEDataHandler, self).__init__(*args, **kwargs)

    def write_h_regs(self, address, words_l, srv_info):
        if address == 4104 and len(words_l) == 2:
            if words_l[0] in self.scf_keys.keys():
                key, ones_complement = tuple(words_l)
                if ones_complement == 65535 - key:
                    if self.scf_cmd_handler is not None:
                        self.scf_cmd_handler(self.scf_keys[key])
                else:
                    logging.debug('Received SCF command, but ones-complement does not match')
            else:
                logging.warning(f"Received unknown SCF command key { words_l[0] }")

        return super().write_h_regs(address, words_l, srv_info)


class DSEEngine(Thread):

    def __init__(self, simulator):
        super().__init__()
        self.simulator = simulator

        self.daemon = True
        self.should_run = False

        self.start_seconds = 10
        self.stop_seconds  = 10

    def start(self):
        logging.info("Engine start")
        self.should_run = True

        self.do_run = True
        self.start_count = 0
        self.stop_count = 0

        self.simulator.add_to_register('/Engine/Starts', 1)

        super().start()

    def stop(self):
        logging.info("Engine stop")
        self.should_run = False

    def run(self):
        while self.do_run:
            if self.should_run:
                if self.start_count < self.start_seconds:
                    self.start_count += 1
                    self._starting()
                else:
                    self._running()
            else:
                self.stop_count += 1
                if self.stop_count <= self.stop_seconds:
                    self._stopping()
                else:
                    self.do_run = False
                    self._stopped()

            self.simulator.update_regs()
            time.sleep(1)
    
    def _starting(self):
        logging.info('Engine state: starting')
        self.simulator.set_register('/StatusCode', 1)
        self.simulator.set_register(f"/StarterVoltage", 12.2 + random.uniform(-0.2, 0.2))

    def _running(self):
        logging.info('Engine state: running')
        self.simulator.set_register('/StatusCode', 3)

        voltage = [
            230 + random.uniform(-2.5, 2.5),
            230 + random.uniform(-2.5, 2.5),
            230 + random.uniform(-2.5, 2.5)
        ]
        current = [
            20 + random.uniform(-5, 5),
            20 + random.uniform(-5, 5),
            20 + random.uniform(-5, 5),
        ]
        power = []

        for i in range(0,3):
            power.append(voltage[i] * current[i])
            self.simulator.set_register(f"/Ac/L{ i+1 }/Voltage", voltage[i])
            self.simulator.set_register(f"/Ac/L{ i+1 }/Current", current[i])
            self.simulator.set_register(f"/Ac/L{ i+1 }/Power", power[i])
        p_sum = sum(power)
        self.simulator.set_register(f"/Ac/Power", p_sum)
        self.simulator.set_register(f"/Ac/Frequency", 50.0 + random.uniform(-1.5, 1.5))

        self.simulator.add_to_register('/Engine/OperatingHours', 1)
        self.simulator.add_to_register('/Ac/Energy/Forward', p_sum / 1000 / 3600)
        self.simulator.add_to_register('/TankLevel', -1/60)
        
        self.simulator.set_register('/StarterVoltage', 14.2 + random.uniform(-0.2, 0.2))
        self.simulator.set_register('/Engine/Speed', 1800 + random.uniform(-10, 10))

    def _stopping(self):
        logging.info('Engine state: stopping')
        self.simulator.set_register('/StatusCode', 4)

        for i in range(0,3):
            self.simulator.set_register(f"/Ac/L{ i+1 }/Voltage", 0)
            self.simulator.set_register(f"/Ac/L{ i+1 }/Current", 0)
            self.simulator.set_register(f"/Ac/L{ i+1 }/Power", 0)
        self.simulator.set_register(f"/Ac/Power", 0)
        self.simulator.set_register(f"/Ac/Frequency", 0)

        self.simulator.set_register('/Engine/Speed', 1800 + random.uniform(-10, 10))
        self.simulator.set_register('/StarterVoltage', 13.4 + random.uniform(-0.2, 0.2))

    def _stopped(self):
        logging.info('Engine state: stopped')

        self.simulator.set_register('/StatusCode', 0)
        self.simulator.set_register('/Engine/Speed', 0)
        self.simulator.set_register('/StarterVoltage', 12.8 + random.uniform(-0.2, 0.2))

class DSEAlarmVals(IntEnum):
    NOT_ACTIVE = 1
    WARNING = 2
    SHUTDOWN = 3
    ELECTRICAL_TRIP = 4
    UNIMPLEMENTED = 15

class DSESimulator:

    alarm_base = 2048
    alarm_count = 26

    scf_keys = {
        35701: 'SELECT_AUTO_MODE',
        35732: 'TELEMETRY_START',
        35733: 'TELEMETRY_STOP'
    }

    alarm_vals = [
        'Disabled digital input',
        'Not active alarm',
        'Warning alarm',
        'Shutdown alarm',
        'Electrical trip alarm',
        'Reserved',
        'Reserved',
        'Reserved',
        'Inactive indication (no string)',
        'Inactive indication (displayed string)',
        'Active indication',
        'Reserved',
        'Reserved',
        'Reserved',
        'Reserved',
        'Unimplemented alarm',
    ]

    server = None
    registers = None
    alarms = None

    def prepare(self, registers, alarms):
        if isinstance(registers, dict):
            self.registers = registers
        elif isinstance(registers, str):
            with open(registers, 'r') as f:
                self.registers = json.load(f)
        else:
            Exception('registers could not be loaded')

        if isinstance(alarms, dict):
            self.alarms = alarms
        elif isinstance(alarms, str):
            with open(alarms, 'r') as f:
                self.alarms = json.load(f)
        else:
            Exception('alarms could not be loaded')

    def start(self, host: str, port: int, no_block=False):

        if not self.registers:
            Exception('registers not loaded, call prepare() first')

        if not self.alarms:
            Exception('alarms not loaded, call prepare() first')

        # Start modbus server
        self.server = ModbusServer(
            host=host,
            port=port,
            data_hdl=DSEDataHandler(
                self.scf_keys,
                self._scf_command_handler
            ),
            no_block=no_block
        )

        # Set basic config
        self.server.data_bank.set_holding_registers(770, [1, 1])     # serial number
        self.server.data_bank.set_holding_registers(768, [1, 4623])  # DSE 4620
        self.server.data_bank.set_holding_registers(4096, [          # GenComm System Control Function capabilities
            0b1111111111111111,
            0b1111111111111111,
            0b1111111111111111,
            0b1111111111111111,
            0b1111111111111111,
            0b1111111111111111,
            0b1111111111111111,
            0b1111111111111111,
        ])

        self.update_regs()
        self.update_alarms()

        self.engine = None
        self.server.start()

    def _set(self, reg: int, val: float, type: str = "u16", scale: int = 1, **kwargs):

        if type == "u16":
            v = [ int(val * scale) if isinstance(val, Number) else 0xffff ]
        elif type == "s16":
            v = [ int(val * scale) & 0xffff if isinstance(val, Number) else 0x7fff ]
        elif type == "u32":
            val = int(val * scale) if isinstance(val, Number) else None
            v = [ val >> 16, val & 0xffff ] if val is not None else [ 0xffff, 0xffff ]
        elif type == "s32":
            val = int(val * scale) & 0xffffffff if isinstance(val, Number) else None
            v = [ val >> 16, val & 0xffff ] if val is not None else [ 0x7fff, 0xffff ]
        else:
            logging.warning(f"unkown type: '{ type }'")
            return

        self.server.data_bank.set_holding_registers(reg, v)

    def update_alarms(self):
        # Set alarms
        alarm_vals = [ 61 ]
        tmp = []
        for alarm in self.alarms:
            if (alarm['val'] not in range(16)):
                logging.warning(f"Invalid alarm value { alarm['val']} for '{ alarm['desc'] }'")
                alarm['val'] = 15  # not implemented
            tmp.append(alarm['val'])
            if len(tmp) == 4:
                # Convert tmp array into one number
                alarm_vals.append(tmp[0] << 12 | tmp[1] << 8 | tmp[2] << 4 | tmp[3])
                tmp = []
        self.server.data_bank.set_holding_registers(self.alarm_base, alarm_vals)

    def update_regs(self):

        # Set regs
        for path, x in self.registers.items():
            val_str = "{:.1f}".format(x['val']) if x['val'] is not None else "NaN"
            logging.info(f"Setting { path } to { val_str }" + ( f" { x['unit'] }" if x['unit'] else '') )
            self._set(**x)

    def _scf_command_handler(self, key):
        logging.info(f"SCF COMMAND RECEIVED: { key }")

        if key == 'TELEMETRY_START':
            if self.engine is None or not self.engine.is_alive():
                self.engine = DSEEngine(self)
                self.engine.start()

        elif key == 'TELEMETRY_STOP':
            if self.engine is not None and self.engine.is_alive():
                self.engine.stop()

        elif key == 'SELECT_AUTO_MODE':
            self.set_register('/AutoStart', 1)
            self.update_regs()

    def stop(self):
        self.server.stop()

    def set_register(self, path: str, value: float):
        self.registers[path]['val'] = value

    def add_to_register(self, path: str, value: float):
        self.registers[path]['val'] += value

    def set_alarm(self, alarm_id, value):
        value = int(value)
        if value not in range(len(self.alarm_vals)):
            return

        for k in self.alarms:
            if k['id'] == alarm_id:
                k['val'] = value
                logging.info(f"Set alarm '{ k['desc'] }' to '{ self.alarm_vals[value] }'")

    def apply_scf_command(self, key):
        self._scf_command_handler(key)


if __name__ == '__main__':

    # parse args
    parser = argparse.ArgumentParser()
    parser.add_argument('-H', '--host', type=str, default='0.0.0.0', help='Host (default: 0.0.0.0)')
    parser.add_argument('-p', '--port', type=int, default=502, help='TCP port (default: 502)')
    parser.add_argument('-d', '--debug', action='store_true', help='set debug mode')
    args = parser.parse_args()

    # logging setup
    if args.debug:
        logging.getLogger('pyModbusTCP.server').setLevel(logging.DEBUG)

    # Load default registers
    with open('dse_registers.json', 'r') as f:
        registers = json.load(f)

    # Load default alarms
    with open('dse_alarms.json', 'r') as f:
        alarms = json.load(f)

    simulator = DSESimulator(
        host=args.host, 
        port=args.port, 
        registers=registers, 
        alarms=alarms
    )
    
    simulator.set_register('/AutoStart', 1)

    # simulator.set_alarm(4096, DSEAlarmVals.SHUTDOWN)            # Emergency stop
    # simulator.set_alarm(4121, DSEAlarmVals.WARNING)             # High battery voltage
    # simulator.set_alarm(4117, DSEAlarmVals.ELECTRICAL_TRIP)     # Magnetic pickup fault

    simulator.start()
