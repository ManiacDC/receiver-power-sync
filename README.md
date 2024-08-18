# Introduction

This script synchronizes the power state of a primary receiver with one or more secondary receivers. When the primary receiver is turned on/off, the secondaries turn on/off. It will also force synchronize every 10 seconds in case a power state was missed.

Currently, only Onkyo receivers are supported, though support for more could be added.

# Configuration

A config.json in the root of the repository can be modified to configure the script.

## Example

```
{
    "primary": {
        "mode": "EISCP",
        "ip": "192.168.1.80"
    },
    "secondaries": [
        {
            "mode": "TCP",
            "ip": "192.168.1.235",
            "tcp_port": 8887
        }
    ]
}
```

## primary

This defines the receiver configuration for the primary receiver.

## secondaries

This is a list of receiver configurations for the secondary receivers.

## Receiver Configuration

### mode

This can be EISCP (for network connected receivers), TCP (for a receiver connected via a serial server such as the NB114), or Serial (computer to receiver) depending on your preferred connection method.

### ip

Needed for EISCP and TCP modes, this is the receiver's IP address. It is recommended you give any receivers a static IP address in your router.

### tcp_port

This is the TCP port for the serial server in TCP mode. Note, this does NOT affect the EISCP port, 60128.

## serial_port

If in Serial mode, the system name of the serial port. On Windows, this will be something like "COM3". On Linux, it will be like "/dev/ttyUSB0".

# Installing dependencies

To install dependencies needed to run the script:
`pip install -r requirements.txt`

If you also want to install tools for development:
`pip install -r requirements.txt -r requirements-dev.txt`

# Running the script

This is designed to be run as a module, so from the root of the repository, you should run:
`python -m receiver_power_sync`

# Running as a service

## Linux

I used this guide to set up the server on Linux (skip to section `Running a Linux daemon`):
https://oxylabs.io/blog/python-script-service-guide

Basically:

 * Create a file named `eiscp_relay.service` in `/etc/systemd/system`
 * Update the file as below
 * Run `systemctl daemon-reload`
 * Run `systemctl start receiver_power_sync`
 * Check that it's running: `systemctl status receiver_power_sync`


I used miniconda to install python, and created a python 3.12 environment. My `receiver_power_sync.service` file looks something like this:

```
[Unit]
Description=Runs receiver-power-sync server
After=syslog.target network.target

[Service]
WorkingDirectory=/home/user/receiver-power-sync
ExecStart=/home/user/miniconda3/envs/rps_env/bin/python -m receiver_power_sync

Restart=always
RestartSec=120

[Install]
WantedBy=multi-user.target
```

## Windows

I would recommend setting up the service using [nssm](https://nssm.cc). I would recommend setting up a miniconda environment with python 3.12 and using that to run the script.
