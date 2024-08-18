"""sends iscp message to the receiver"""

import select
import socket
import time
from logging import DEBUG, WARNING, Logger
from typing import List, Optional

import serial

from .config import Config, ReceiverConfig
from .constants import PORT
from .eiscp import build_eiscp_packet, extract_eiscp_header


class ConnectionClosedException(Exception):
    """raised when connection is closed"""


class ReceiverConnection:
    """listens for ISCP messages from receiver"""

    logger: Logger
    connected: bool

    def __new__(cls, logger: Logger, rec_config: ReceiverConfig, *args, **kwargs):

        if cls == ReceiverConnection:
            if rec_config["mode"] == "Serial":
                return IscpSerialConnection(logger, rec_config, *args, **kwargs)
            if rec_config["mode"] == "TCP":
                return IscpTcpConnection(logger, rec_config, *args, **kwargs)
            if rec_config["mode"] == "EISCP":
                return EiscpConnection(logger, rec_config, *args, **kwargs)
            raise ValueError(f"invalid value for config mode: {rec_config['mode']}")

        return object.__new__(cls)

    def __init__(self, logger: Logger, rec_config: ReceiverConfig, message_callback: Optional[callable]):
        self.logger = logger
        self.rec_config = rec_config
        self.connected = False
        self.message_callback = message_callback

    def __exit__(self, _type, value, traceback):
        self._disconnect()

    def __enter__(self):
        return self

    def _connect_to_receiver(self):
        raise NotImplementedError("implement in subclass")

    def _disconnect(self):
        raise NotImplementedError("implement in subclass")

    def listen_forever(self):
        """listens for ISCP messages from receiver"""

        while True:
            if not self.connected:
                try:
                    self._connect_to_receiver()
                except Exception:  # pylint: disable = broad-exception-caught
                    time.sleep(1)
                    continue
            try:
                ready = self.check_for_message()
                if ready:
                    message = self.get_message()
                    if self.message_callback:
                        self.message_callback(message)
            except ConnectionResetError:
                self._disconnect()

    def check_for_message(self):
        """checks for messages"""
        raise NotImplementedError("implement in subclass")

    def get_message(self):
        """receives data on a TCP socket and ensures it's terminated"""
        received_data = b""
        terminated = False
        found_message = False
        while self.check_for_message():
            data = self._get_one_byte()
            if not data:
                raise ConnectionResetError("connection closed")
            if data in (b"\r", b"\n", b"\x1A"):
                if found_message:
                    terminated = True
                    break
                continue
            if data == b"!":
                found_message = True
            received_data += data

        self.logger.log(DEBUG if terminated else WARNING, "total received %s, terminated %s", received_data, terminated)

        if terminated:
            return received_data

        return None

    def _get_one_byte(self):
        raise NotImplementedError("implement in subclass")

    def _prep_message_for_receiver(self, message: bytes):
        raise NotImplementedError("implement in subclass")

    def send_message_to_receiver(self, message: bytes):
        """sends a message to the receiver"""
        if not self.connected:
            self._connect_to_receiver()
        message = self._prep_message_for_receiver(message)
        try:
            self._send_message_to_receiver(message)
        except ConnectionResetError:
            self.logger.debug("not connected to receiver, trying again")
            time.sleep(1)
            self._disconnect()
            self._connect_to_receiver()
            self._send_message_to_receiver(message)

    def _send_message_to_receiver(self, message: bytes):
        raise NotImplementedError("implement in subclass")


class EiscpConnection(ReceiverConnection):
    """listens for ISCP messages from receiver"""

    sock: socket.socket

    def __init__(self, logger: Logger, rec_config: ReceiverConfig, message_callback: Optional[callable]):
        self.sock = None
        super().__init__(logger, rec_config, message_callback)

    def _connect_to_receiver(self):
        try:
            if not self.sock:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.rec_config["ip"], PORT))
            self.logger.info("Connected to receiver at: %s:%s", self.rec_config["ip"], PORT)
        except Exception as err:
            self.logger.exception("unable to connect to receiver: %s:%s", self.rec_config["ip"], PORT)
            raise err

        self.connected = True

    def _disconnect(self):
        """disconnects from the receiver"""
        if self.connected:
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
            self.sock = None
            self.connected = False
            self.logger.info("disconnected from receiver")

    def check_for_message(self):
        """returns true if a message is ready"""
        return select.select([self.sock], [], [], 0.1)[0]

    def get_message(self):
        """receives data on a TCP socket and ensures it's terminated"""
        header: bytes = b""
        while self.check_for_message():
            data = self._tcp_grab_bytes(1)
            if data == b"I":
                header += data
                break
            if not data:
                raise ConnectionClosedException()

        header += self._tcp_grab_bytes(15)

        header_data = extract_eiscp_header(header, self.logger)

        if not header_data:
            self.logger.debug("request did not have a valid header")
            return

        if header_data[0] > 16:
            # grab remaining header data
            self._tcp_grab_bytes(header_data[0] - 16)

        message = self._tcp_grab_bytes(header_data[1])

        if not message:
            self.logger.debug("request did not contain data segment")
            return

        while message.endswith(b"\r") or message.endswith(b"\n") or message.endswith(b"\x1A"):
            message = message[:-1]

        self.logger.debug("request message was %s", message)

        if not message.startswith(b"!1"):
            self.logger.debug("request message did not begin with !1")
            return

        return message

    def _tcp_grab_bytes(self, num_bytes: int):
        """grabs num_bytes bytes from tcp buffer"""
        data = b""
        for _ in range(num_bytes):
            ready = select.select([self.sock], [], [], 1)[0]
            if ready:
                data += self.sock.recv(1)
            else:
                # timeout hit, did not receive expected bytes
                return None
        return data

    def _prep_message_for_receiver(self, message):
        """preps the message for the receiver"""
        return build_eiscp_packet(message)

    def _send_message_to_receiver(self, message: bytes):
        self.sock.sendall(message)

    def _get_one_byte(self):
        pass


class IscpTcpConnection(ReceiverConnection):
    """listens for TCP ISCP messages from receiver"""

    sock: socket.socket

    def __enter__(self):
        return self

    def __exit__(self, _type, value, traceback):
        self._disconnect()

    def _disconnect(self):
        """disconnects from the receiver"""
        if self.connected:
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
            self.sock = None
            self.connected = False
            self.logger.info("disconnected from receiver")

    def __init__(self, logger: Logger, rec_config: ReceiverConfig, message_callback: Optional[callable]):
        self.sock = None
        super().__init__(logger, rec_config, message_callback)

    def _connect_to_receiver(self):
        try:
            if not self.sock:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.rec_config["ip"], self.rec_config["tcp_port"]))
            self.logger.info("Connected to receiver at: %s:%s", self.rec_config["ip"], self.rec_config["tcp_port"])
        except Exception as err:
            self.logger.exception(
                "unable to connect to serial server: %s:%s", self.rec_config["ip"], self.rec_config["tcp_port"]
            )
            raise err

        self.connected = True

    def check_for_message(self):
        """returns true if a message is ready"""
        return select.select([self.sock], [], [], 0.1)[0]

    def _get_one_byte(self):
        return self.sock.recv(1)

    def _prep_message_for_receiver(self, message: bytes):
        return message + b"\r"

    def _send_message_to_receiver(self, message: bytes):
        self.sock.sendall(message)


class IscpSerialConnection(ReceiverConnection):
    """listens for Serial ISCP messages from receiver"""

    ser: serial.Serial

    def __enter__(self):
        return self

    def __exit__(self, _type, value, traceback):
        self._disconnect()

    def _disconnect(self):
        """disconnects from the receiver"""
        if self.connected and self.ser.is_open:
            self.ser.close()
            self.logger.info("disconnected from receiver")

    def __init__(self, logger: Logger, rec_config: ReceiverConfig, message_callback: Optional[callable]):
        self.ser = None
        super().__init__(logger, rec_config, message_callback)

    def _connect_to_receiver(self):
        try:
            if not self.ser:
                self.ser = serial.Serial(self.rec_config["serial_port"], 9600, timeout=0.1, write_timeout=0.5)
            if not self.ser.is_open:
                self.ser.open()
            self.logger.info("Connected to receiver at: %s", self.rec_config["serial_port"])
        except Exception as err:
            self.logger.exception(
                "unable to connect to serial port: %s",
                self.rec_config["serial_port"],
            )
            raise err

        self.connected = True

    def check_for_message(self):
        """returns true if a message is ready"""
        in_waiting = self.ser.in_waiting
        if in_waiting > 0:
            return True
        else:
            # implement timeout since in_waiting doesn't have one
            time.sleep(0.1)
            in_waiting = self.ser.in_waiting
            if in_waiting > 0:
                return True
        return False

    def _get_one_byte(self):
        return self.ser.read(1)

    def _prep_message_for_receiver(self, message: bytes):
        return message + b"\r"

    def _send_message_to_receiver(self, message: bytes):
        self.ser.write(message)


class ReceiverSyncService:
    """listens for power command messages from primary and relays them to secondary"""

    logger: Logger
    config: Config
    listeners: List[ReceiverConnection]

    def __enter__(self):
        return self

    def __exit__(self, _type, value, traceback):
        for listener in self.listeners:
            listener._disconnect()

    def __init__(self, logger: Logger, config: Config):
        self.logger = logger
        self.config = config
        self.listeners = [ReceiverConnection(logger, config["primary"], self.relay_message_to_secondary)]
        for rec_config in config["secondaries"]:
            self.listeners.append(ReceiverConnection(logger, rec_config, None))

    def send_pwr_question_to_primary(self):
        """queries power state on the primary"""
        self.logger.debug("sending !1PWRQSTN to primary")
        self.listeners[0].send_message_to_receiver(b"!1PWRQSTN")

    def relay_message_to_secondary(self, message: bytes):
        """relays a message from the primary receiver to the secondary"""
        if message.startswith(b"!1PWR"):
            self.logger.debug(f"relaying power message {message}")
            for listener in self.listeners[1:]:
                listener.send_message_to_receiver(message)
