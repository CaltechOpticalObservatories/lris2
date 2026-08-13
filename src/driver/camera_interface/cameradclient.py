"""
Camerad Interface (Archon controller telemetry client)
"""
import socket
from typing import Final, Optional, Union

from hardware_device_base import HardwareSensorBase

StatusValue = Union[int, float, str]

RECV_CHUNK: Final[int] = 8192
DONE: Final[bytes] = b"DONE"
ERROR: Final[bytes] = b"ERROR"


class CameradClient(HardwareSensorBase):
    """Client for camerad's blocking TCP command port (BLKPORT).

    camerad is a plain-text, request/response server: each command is sent on
    its own short-lived TCP connection and answered with space-separated
    `KEY=VALUE` tokens terminated by `DONE` (or `ERROR`). The Archon controller
    itself is a separate, longer-lived session opened/closed via camerad's
    `open`/`close` commands, which this class issues from `connect()`/
    `disconnect()`. Telemetry is read read-only via `native STATUS`/
    `native FRAME` passthrough to the Archon controller.
    """

    def __init__(self, log: bool = True, logfile: str = __name__.rsplit(".", 1)[-1],
                 timeout: float = 5.0):
        """Initialize the CameradClient class.
        Args:
            log (bool): If True, start logging.
            logfile (str, optional): Path to log file.
            timeout (float, optional): Per-command socket timeout in seconds.
        """
        super().__init__(log, logfile)
        self.timeout = timeout
        self.host: Optional[str] = None
        self.port: Optional[int] = None
        self.sock: Optional[socket.socket] = None
        self._telemetry: dict[str, StatusValue] = {}
        self._status_raw: str = ""
        self._frame_raw: str = ""

    def connect(self, host, port, con_type="tcp") -> None:  # pylint: disable=W0221
        """Point the client at a camerad endpoint (BLKPORT) and open the controller."""
        if con_type != "tcp":
            self.report_error(f"Unsupported con_type: {con_type}")
            return
        if not self.validate_connection_params((host, port)):
            self.report_error(f"Invalid connection arguments: {host}:{port}")
            return

        self.host, self.port = host, port
        self._set_connected(True)
        if self.send_command("open") is None:
            self.report_error(f"Failed to open controller at {host}:{port}")
            self._set_connected(False)
            return
        self.report_info(f"Opened camerad controller at {host}:{port}")

    def disconnect(self) -> None:
        """Close the controller session opened by connect()."""
        if self.is_connected():
            self.send_command("close")
        self._set_connected(False)
        self.report_info("Closed camerad controller")

    def _send_command(self, command: str) -> bool:  # pylint: disable=W0221
        """Open a fresh connection to camerad and send one command."""
        if not self.is_connected():
            self.report_error("Controller not connected")
            return False
        try:
            with self.lock:
                self.sock = socket.create_connection(
                    (self.host, self.port), timeout=self.timeout)
                self.sock.sendall(f"{command}\n".encode())
        except OSError as ex:
            self.report_error(f"Failed to send command {command!r}: {ex}")
            return False
        return True

    def _read_reply(self) -> Optional[str]:
        """Read camerad's reply until DONE/ERROR, then close the connection."""
        if self.sock is None:
            self.report_error("No active command socket")
            return None
        try:
            buf = bytearray()
            while True:
                chunk = self.sock.recv(RECV_CHUNK)
                if not chunk:
                    break
                buf.extend(chunk)
                if buf.rstrip().endswith((DONE, ERROR)):
                    break
        except OSError as ex:
            self.report_error(f"Failed to read reply: {ex}")
            return None
        finally:
            self.sock.close()
            self.sock = None

        reply = bytes(buf).decode(errors="replace").rstrip()
        if reply.endswith("ERROR"):
            self.report_error("camerad returned ERROR")
            return None
        if not reply.endswith("DONE"):
            self.report_error(f"unterminated reply: {reply!r}")
            return None
        return reply[: -len("DONE")].rstrip()

    def send_command(self, command: str) -> Optional[str]:
        """Send one command and return its reply text, or None on failure."""
        if not self._send_command(command):
            return None
        return self._read_reply()

    @staticmethod
    def _coerce_value(token: str) -> StatusValue:
        """Convert a token to int/float, or keep as str when leading zeros matter."""
        if len(token) > 1 and token[0] == "0" and token.isdigit():
            return token
        try:
            return int(token)
        except ValueError:
            pass
        try:
            return float(token)
        except ValueError:
            return token

    @classmethod
    def _parse_reply(cls, reply: str) -> dict[str, StatusValue]:
        """Parse a `KEY=VALUE ...` reply into a `{key: value}` mapping."""
        values: dict[str, StatusValue] = {}
        for token in reply.split():
            if "=" not in token:
                continue
            key, _, value = token.partition("=")
            values[key] = cls._coerce_value(value)
        return values

    def poll_status(self) -> dict[str, StatusValue]:
        """Query `native STATUS`, cache and return the parsed fields."""
        reply = self.send_command("native STATUS")
        if reply is None:
            raise IOError("Failed to read STATUS from camerad")
        self._status_raw = reply
        values = self._parse_reply(reply)
        self._telemetry.update(values)
        return values

    def poll_frame(self) -> dict[str, StatusValue]:
        """Query `native FRAME`, cache and return the parsed fields."""
        reply = self.send_command("native FRAME")
        if reply is None:
            raise IOError("Failed to read FRAME from camerad")
        self._frame_raw = reply
        values = self._parse_reply(reply)
        self._telemetry.update(values)
        return values

    @property
    def telemetry(self) -> dict[str, StatusValue]:
        """Return a copy of the last-polled telemetry fields."""
        return dict(self._telemetry)

    @property
    def status_raw(self) -> str:
        """Return the last raw `native STATUS` reply text."""
        return self._status_raw

    @property
    def frame_raw(self) -> str:
        """Return the last raw `native FRAME` reply text."""
        return self._frame_raw

    def get_atomic_value(self, item: str = "") -> Optional[StatusValue]:
        """Return the cached value for a telemetry field, or None if unknown."""
        return self._telemetry.get(item)
