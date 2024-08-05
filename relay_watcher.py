#! /usr/bin/python3 -u

import os
import logging
import asyncio

from dse import DSESimulator

class DbusRelayWatcher():

    def __init__(self, simulator: DSESimulator):
        self.s = simulator
        self.state = False

    async def run(self):
        try:
            import dbus

            while True:
                bus = dbus.SessionBus() if 'DBUS_SESSION_BUS_ADDRESS' in os.environ else dbus.SystemBus()
                res = bus.call_blocking('com.victronenergy.system', '/Relay/0/State', None, 'GetValue', '', []) > 0

                if res != self.state:
                    # Start or stop generator based on relay state
                    self.s.apply_scf_command(
                        'TELEMETRY_START' if res else 'TELEMETRY_STOP'
                    )
                    self.state = res

                await asyncio.sleep(1)

        except:
            logging.exception("DBus Relay Watcher excited unexpectedly:")