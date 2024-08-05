# DSE Modbus Simulator

This repository contains a Python script simulating the Modbus TCP server of a generator equipped with a DSE 4620 controller + DSE 855 "USB to Ethernet Communications Device".

## Features

**Modbus:**
* Telemetry Start/Stop
* Setting into Remote start mode
* Power production value simulation (randomized)
* Alerts

**Web interface:**
* Read and set register values
* Set via web interface

![DSE Modbus Simulator Web Interface](./.github/webinterface.png)

## Get started

Follow these steps to run the simulator on your machine:

```sh
# Install virtualenv
pip3 install virtualenv

# Create venv
python3 -m venv venv

# Activate venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run Webserver at http://localhost:8000 and Modbus server on 0.0.0.0:502
python3 main.py
```

After that, you can enter your machine's IP address on the GX device at *Settings* > *Modbus TCP/UDP devices* > *Saved Devices* via the **Add** button. Use `TCP`, port `502` and unit id `1`. After that, the simulated generator should show up in the Device list.

### Helper relay mode

Some DSE controllers, esp. the DSE 4520 MKII model, do not support starting and stopping via Modbus. This can also be simulated using `-hr` flag, by which the controller does not advertise the capability of being remotely started or stopped via Modbus. If the `dbus` Python dependency is available, it will watch for the value of the `/Relay/0/State` path of `com.victronenergy.system` and trigger a start or stop of the simulated genset based on its value change, simultating the physical controller start/stop IO input to be wired to Relay 1 of a GX device.