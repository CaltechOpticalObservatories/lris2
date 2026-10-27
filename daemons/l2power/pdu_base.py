"""Shared base class for the l2power PDU daemons.

Each PDU family gets a daemon script in this directory that subclasses
PduDaemon and only says how to talk to its hardware. Hardware methods raise
on failure, so the keyword that called them reports the reason.
"""

import argparse
import os
import re
import sys
from collections.abc import Callable
from typing import Any

from lris2.daemon import Lris2Daemon

# Errors a hardware call raises when the PDU refuses or garbles a command
HARDWARE_ERRORS = (RuntimeError, ValueError, OSError)


class PduDaemon(Lris2Daemon):  # pylint: disable=W0223
    """Base class for a daemon that controls one networked PDU."""

    default_port = 23

    def __init__(self) -> None:
        """Set defaults; a subclass then sets self.dev to its vendor driver."""
        super().__init__()
        self.host: str | None = None
        self.port = self.default_port
        self.username: str | None = None
        self.password: str | None = None
        self.outlet_count = 0
        self.outlet_names: dict[int, str] = {}
        self.dev: Any = None

    def connect(self) -> bool:
        """Open a session to the PDU, True when it is up."""
        raise NotImplementedError

    def disconnect(self) -> None:
        """Close the session, tolerating one that was never opened."""
        raise NotImplementedError

    def is_connected(self) -> bool:
        """Return True while a session to the PDU is open."""
        raise NotImplementedError

    def initialize(self) -> bool:
        """Read the PDU's device properties after connect(), True on success."""
        raise NotImplementedError

    def reported_outlet_count(self) -> int | None:
        """Return the outlet count the PDU reports, or None when it cannot say."""
        raise NotImplementedError

    def get_model(self) -> str:
        """Return the PDU model."""
        raise NotImplementedError

    def get_firmware(self) -> str:
        """Return the PDU firmware revision."""
        raise NotImplementedError

    def get_outlet_state(self, n: int) -> bool:
        """Return True when outlet ``n`` is powered."""
        raise NotImplementedError

    def set_outlet_state(self, n: int, on: bool) -> None:
        """Switch outlet ``n`` on or off."""
        raise NotImplementedError

    def get_outlet_name(self, n: int) -> str:
        """Return the name configured on the PDU for outlet ``n``."""
        raise NotImplementedError

    def set_outlet_name(self, n: int, name: str) -> None:
        """Rename outlet ``n`` on the PDU."""
        raise NotImplementedError

    def get_outlet_switchable(self, n: int) -> bool:
        """Return True when outlet ``n`` may be switched, False when locked."""
        raise NotImplementedError

    def set_outlet_switchable(self, n: int, switchable: bool) -> None:
        """Unlock outlet ``n`` for switching, or lock it where it is."""
        raise NotImplementedError

    def register_device_keywords(self) -> None:
        """Register the keywords that describe the whole PDU."""
        self.keyword_registry.string("model",
                                     getter=self.when_connected("model", self.get_model),
                                     description="PDU model, as reported by the hardware.")
        self.keyword_registry.string("firmware",
                                     getter=self.when_connected("firmware", self.get_firmware),
                                     description="PDU firmware revision.")

    def register_outlet_keywords(self, n: int) -> None:
        """Register the keywords for outlet ``n``."""
        key = self.outlet_key(n)
        self.keyword_registry.bool(
            f"state{key}",
            getter=self.when_connected(f"state{key}", self.get_outlet_state, n),
            setter=self.when_connected(f"state{key}", self.set_outlet_state, n),
            description=f"Outlet {n} power state; write true/false to switch on/off.")
        self.keyword_registry.string(
            f"name{key}",
            getter=self.when_connected(f"name{key}", self.get_outlet_name, n),
            setter=self.when_connected(f"name{key}", self.set_outlet_name, n),
            description=f"Outlet {n} name, as configured on the PDU.")
        self.keyword_registry.bool(
            f"switchable{key}",
            getter=self.when_connected(f"switchable{key}", self.get_outlet_switchable, n),
            setter=self.when_connected(f"switchable{key}", self.set_outlet_switchable, n),
            description=f"Whether outlet {n} can be switched (True) or is locked "
                        "in its current state (False); write to lock/unlock it.")

    def outlet_key(self, n: int) -> str:
        """Return the suffix naming outlet ``n`` in its keywords.

        ``_<name>`` when hardware.outlet_names gives it a name, otherwise the
        outlet number.
        """
        name = self.outlet_names.get(n)
        return f"_{name}" if name else str(n)

    def when_connected(self, label: str, func: Callable[..., Any],
                       *args: Any) -> Callable[..., Any]:
        """Wrap a hardware call for a keyword so failures reach lasterror."""
        def call(*value: Any) -> Any:
            if not self._connected():
                raise self._error(f"{label}: not connected to the PDU")
            try:
                return func(*args, *value)
            except HARDWARE_ERRORS as e:
                raise self._error(f"{label}: {e}") from e
        return call

    def on_start(self, libby) -> None:  # pylint: disable=W0613
        """Read config, register keywords, and connect to the PDU."""
        self.host = self.get_config("hardware.ip_address")
        self.port = int(self.get_config("hardware.tcp_port", self.default_port))
        self.username = self._credential("username")
        self.password = self._credential("password")
        self.outlet_count = int(self.get_config("hardware.outlet_count", 0))
        if self.outlet_count < 1:
            self.logger.error("hardware.outlet_count must be a positive integer")
            return
        try:
            self.outlet_names = self._parse_outlet_names(
                self.get_config("hardware.outlet_names"))
        except ValueError as e:
            self.logger.error("%s", e)
            return

        # Keywords register before the connect so the daemon stays inspectable
        # while the PDU is unreachable
        self._register_keywords()

        try:
            self._set_connected(True)
            self.logger.info("Connected to PDU at %s:%s", self.host, self.port)
        except RuntimeError:
            self.logger.warning("Daemon will start but hardware is not available")

    def on_stop(self, libby=None) -> None:  # pylint: disable=W0613
        """Disconnect from the PDU."""
        self.disconnect()
        self.logger.info("Disconnected from PDU")

    def _register_keywords(self) -> None:
        self.keyword_registry.bool("isconnected",
                                   getter=self._connected,
                                   setter=self._set_connected,
                                   description="Whether the daemon can talk to the PDU.")
        self.keyword_registry.int("outletcount",
                                  getter=lambda: self.outlet_count,
                                  description="Number of outlets configured for this PDU.")
        self.keyword_registry.string("status",
                                     getter=self.when_connected(
                                         "status", lambda: str(self.dev.get_status())),
                                     description="Driver status as a (code, message) string.")
        self.keyword_registry.trigger("shutdown",
                                      action=self._shutdown,
                                      description="Disconnect from the PDU and stop the daemon.")
        self.register_device_keywords()
        for n in range(1, self.outlet_count + 1):
            self.register_outlet_keywords(n)

    def _connected(self) -> bool:
        return self.dev is not None and bool(self.is_connected())

    def _set_connected(self, connect: bool) -> None:
        if not connect:
            self.disconnect()
            return
        if not (self.host and self.username and self.password):
            raise self._error("hardware.ip_address, username and password are all required")
        try:
            # The drivers report a refused connection to their own logger and
            # return normally, so check the result rather than trusting the call
            if not (self.connect() and self.is_connected() and self.initialize()):
                raise RuntimeError("driver reported failure")
        except HARDWARE_ERRORS as e:
            raise self._error(f"cannot connect to PDU at {self.host}:{self.port}: {e}") from e
        reported = self.reported_outlet_count()
        if reported and reported != self.outlet_count:
            self.logger.warning("hardware.outlet_count is %d but the PDU reports %d",
                                self.outlet_count, reported)

    def _shutdown(self) -> None:
        self.logger.info("Shutting down")
        self.disconnect()
        self.request_stop()

    def _error(self, message: str) -> RuntimeError:
        """Log a failure so lasterror carries it, and return it for raising."""
        self.logger.error("%s", message)
        return RuntimeError(message)

    @staticmethod
    def _confirm(ok: bool, action: str) -> None:
        """Raise when a driver call reports that it refused to act."""
        if not ok:
            raise RuntimeError(f"driver refused to {action}")

    def _credential(self, name: str) -> str | None:
        """Read a login credential from config, inline or from the environment."""
        value = self.get_config(f"hardware.{name}")
        if value:
            return str(value)
        env_name = self.get_config(f"hardware.{name}_env")
        if not env_name:
            return None
        value = os.environ.get(str(env_name))
        if not value:
            self.logger.error("hardware.%s_env names %s, which is unset or empty",
                              name, env_name)
        return value or None

    def _parse_outlet_names(self, raw: Any) -> dict[int, str]:
        """Validate hardware.outlet_names, a map of outlet number to keyword name.

        Characters other than letters, digits and underscores become
        underscores. Raises ValueError on a bad entry.
        """
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise ValueError("hardware.outlet_names must map outlet numbers to names")
        names: dict[int, str] = {}
        for key, raw_name in raw.items():
            try:
                n = int(key)
            except (TypeError, ValueError):
                raise ValueError(f"hardware.outlet_names: '{key}' is not an outlet number") \
                    from None
            if not 1 <= n <= self.outlet_count:
                raise ValueError(f"hardware.outlet_names: outlet {n} is outside "
                                 f"1..{self.outlet_count}")
            name = re.sub(r"[^A-Za-z0-9_]", "_", "" if raw_name is None else str(raw_name))
            if not name:
                raise ValueError(f"hardware.outlet_names: outlet {n} name is empty")
            if name.lower() in (other.lower() for other in names.values()):
                raise ValueError(f"hardware.outlet_names: name '{name}' is used twice")
            names[n] = name
        return names


def main(daemon_class: type[PduDaemon], description: str) -> None:
    """Run a PDU daemon from the command line."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('-c', '--config', type=str, required=True,
                        help='Path to config file (YAML)')
    args = parser.parse_args()

    try:
        daemon_class.from_config_file(args.config).serve()
    except KeyboardInterrupt:
        print("\nDaemon interrupted by user")
        sys.exit(0)
    except Exception as e:  # pylint: disable=W0718
        print(f"Error running daemon: {e}", file=sys.stderr)
        sys.exit(1)
