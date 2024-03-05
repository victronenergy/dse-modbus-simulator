# DSE Modbus Simulator

This repository contains a Python script simulating a generator controlled by a Deep Sea Electronics DSE 4620 controller.

## Features

* Telemetry Start/Stop
* Setting into Auto-Mode
* Power production value simulation (randomized)
* Alerts

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

# Run
python3 main.py -d

```