"""reads configuration files for the relay"""

import json
import os
from pathlib import Path
from typing import List, Literal, Optional, TypedDict


class ConfigError(Exception):
    """raised when a config error occurs"""


class ReceiverConfig(TypedDict):
    """receiver config"""

    mode: Literal["EISCP", "TCP", "Serial"]
    ip: Optional[str] = None
    tcp_port: Optional[int] = None
    serial_port: Optional[str] = None


class Config(TypedDict):
    """configuration class"""

    primary: ReceiverConfig
    secondaries: List[ReceiverConfig]


def validate_receiver(rec_config: ReceiverConfig):
    """validates the receiver config"""
    if "mode" not in rec_config:
        raise ConfigError("config missing mode")

    if rec_config["mode"] == "EISCP":
        if "ip" not in rec_config or rec_config["ip"] in (None, ""):
            raise ConfigError("ip missing for EISCP")

    elif rec_config["mode"] == "TCP":
        if "ip" not in rec_config or rec_config["ip"] in (None, ""):
            raise ConfigError("ip missing for TCP")

        if "tcp_port" not in rec_config or rec_config["tcp_port"] in (None, ""):
            raise ConfigError("tcp_port missing for TCP")

    elif rec_config["mode"] == "Serial":
        if "serial_port" not in rec_config or rec_config["serial_port"] in (None, ""):
            raise ConfigError("serial_port missing for Serial")

    else:
        raise ConfigError(f'invalid mode: {rec_config["mode"]}')


def get_config_path() -> Path:
    """returns the path to the configuration file"""
    env_path = os.environ.get("RPS_CONFIG_PATH")
    if env_path:
        return Path(env_path).expanduser()

    default_path = Path(".", "config.json")
    if default_path.exists():
        return default_path

    docker_path = Path("/config/config.json")
    if docker_path.exists():
        return docker_path

    return default_path


def get_config():
    """gets the config"""
    config_path = get_config_path()

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found at '{config_path}'") from exc

    for key in ["primary", "secondaries"]:
        if key not in config:
            raise ConfigError(f"config missing '{key}'")

    validate_receiver(ReceiverConfig(config["primary"]))
    config["primary"] = ReceiverConfig(config["primary"])

    for i, rec in enumerate(config["secondaries"]):
        validate_receiver(ReceiverConfig(rec))
        config["secondaries"][i] = ReceiverConfig(rec)

    config = Config(config)

    return config
