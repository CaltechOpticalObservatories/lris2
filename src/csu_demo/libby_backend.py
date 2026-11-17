"""coo-ethercat axis backend that drives the bars through the ``lris2.csu`` daemon."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Sequence
from typing import Any, Final, Protocol

from cooethercat import AxisError, CoeType, ControllerState, MoveMode
from cooethercat.config import AxisConfig

# One status read serves every bar's poll within this window
_STATUS_TTL_S: Final = 0.1


class KeywordClient(Protocol):
    """The slice of ``libby.Client`` this backend uses."""

    def get(self, name: str, *, timeout_s: float = ...) -> Any:
        """Read a keyword's value."""

    def set(self, name: str, value: Any, *, timeout_s: float | None = None) -> Any:
        """Write a keyword."""


def bar_number(axis: AxisConfig) -> int:
    """Return N for a bar named CSU-N, the suffix of its daemon keywords."""
    return int(axis.name.rsplit("-", 1)[1])


class LibbyBackend:
    """Axis backend speaking to the CSU daemon's keywords instead of the PLC."""

    def __init__(self, client: KeywordClient, peer: str = "lris2.csu",
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._client = client
        self._peer = peer
        self._clock = clock
        self._lock = threading.Lock()
        self._status: dict[str, dict[str, Any]] = {}
        self._status_time = float("-inf")
        # The daemon takes absolute targets, so a move is assembled here before it is sent
        self._pending: dict[str, dict[str, Any]] = {}

    def open(self) -> None:
        self._invalidate()

    def close(self) -> None:
        self._invalidate()

    def read_field(self, axis: AxisConfig, field: str) -> Any:
        if field == "velocity":
            return self._get(f"velocity{bar_number(axis)}")
        try:
            return self._bar_status(axis)[field]
        except KeyError:
            raise AxisError(f"{axis.name}: the CSU daemon does not report {field!r}") from None

    def read_fields(self, axis: AxisConfig, fields: Sequence[str]) -> dict[str, Any]:
        status = self._bar_status(axis)
        return {field: status[field] for field in fields}

    def write_field(self, axis: AxisConfig, field: str, value: Any) -> None:
        n = bar_number(axis)
        match field:
            case "enable":
                self._set(f"isenabled{n}", bool(value))
            case "velocity":
                self._set(f"velocity{n}", float(value))
            case "mode" | "target":
                self._pending.setdefault(axis.name, {})[field] = value
            case _:
                raise AxisError(f"{axis.name}: {field!r} cannot be set through the CSU daemon")

    def fire_trigger(self, axis: AxisConfig, field: str) -> None:
        n = bar_number(axis)
        match field:
            case "move":
                self._set(f"positionvalue{n}", self._target(axis))
            case "stop":
                self._set(f"halt{n}", True)
            case "reset":
                self._set(f"reset{n}", True)
            case _:
                raise AxisError(f"{axis.name}: {field!r} is not available through the CSU daemon")

    def read_object(self, axis: AxisConfig, index: int, subindex: int, kind: CoeType) -> int:
        raise AxisError(f"{axis.name}: CoE objects are served as telemetry keywords, not here")

    def controller_state(self) -> ControllerState:
        return ControllerState(self._get("plcstate"))

    def _target(self, axis: AxisConfig) -> float:
        pending = self._pending.pop(axis.name, {})
        if "target" not in pending:
            raise AxisError(f"{axis.name}: move fired without a target")
        target = float(pending["target"])
        if pending.get("mode") == MoveMode.RELATIVE:
            self._invalidate()
            target += float(self._bar_status(axis)["position"])
        return target

    def _bar_status(self, axis: AxisConfig) -> dict[str, Any]:
        with self._lock:
            if self._clock() - self._status_time > _STATUS_TTL_S:
                self._status = json.loads(self._get("status"))
                self._status_time = self._clock()
            return self._status[axis.name]

    def _invalidate(self) -> None:
        with self._lock:
            self._status_time = float("-inf")

    def _get(self, keyword: str) -> Any:
        return self._client.get(f"{self._peer}.{keyword}")

    def _set(self, keyword: str, value: Any) -> None:
        self._client.set(f"{self._peer}.{keyword}", value)
        self._invalidate()
