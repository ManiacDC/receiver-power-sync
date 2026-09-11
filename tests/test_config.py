import json

import pytest

from receiver_power_sync.config import ConfigError, get_config


def test_get_config_reads_default_config_file(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "primary": {"mode": "EISCP", "ip": "192.168.1.10"},
                "secondaries": [{"mode": "EISCP", "ip": "192.168.1.11"}],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    config = get_config()

    assert config["primary"]["ip"] == "192.168.1.10"
    assert config["secondaries"][0]["ip"] == "192.168.1.11"


def test_get_config_reads_overridden_path(tmp_path, monkeypatch):
    config_path = tmp_path / "mounted-config.json"
    config_path.write_text(
        json.dumps(
            {
                "primary": {"mode": "EISCP", "ip": "10.0.0.10"},
                "secondaries": [{"mode": "EISCP", "ip": "10.0.0.11"}],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RPS_CONFIG_PATH", str(config_path))

    config = get_config()

    assert config["primary"]["ip"] == "10.0.0.10"
    assert config["secondaries"][0]["ip"] == "10.0.0.11"


@pytest.mark.parametrize(
    "payload",
    [
        {"primary": {"mode": "EISCP", "ip": None}, "secondaries": [{"mode": "EISCP", "ip": "192.168.1.11"}]},
        {"primary": {"mode": "TCP", "ip": "192.168.1.10", "tcp_port": None}, "secondaries": []},
        {"primary": {"mode": "Serial", "serial_port": None}, "secondaries": []},
    ],
)
def test_get_config_rejects_missing_required_values(tmp_path, monkeypatch, payload):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    with pytest.raises(ConfigError):
        get_config()
