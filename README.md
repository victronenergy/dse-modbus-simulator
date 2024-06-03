# DSE Modbus Simulator

This repository contains a Python script simulating a generator controlled by a Deep Sea Electronics DSE 4620 controller.

## Features

**Modbus:**
* Telemetry Start/Stop
* Setting into Auto-Mode
* Power production value simulation (randomized)
* Alerts

**Webserver:**
* Read and set register values and alarms via web interface

## Start

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
uvicorn main:app
```