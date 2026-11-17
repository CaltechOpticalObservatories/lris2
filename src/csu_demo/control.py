"""Axis status cache and single-operator control over a coo-ethercat AxisSet."""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from cooethercat import Axis, AxisError, AxisSet

from .presets import PresetError, PresetStore, SavedBar

_POLL_PERIOD_S: Final = 0.25
LEASE_S: Final = 15.0


class ControlError(RuntimeError):
    """Raised when a command is refused before it reaches an axis."""


@dataclass
class _Lease:
    """Who may command axes, and until when."""

    token: str
    holder: str
    expires: float


class Controller:
    """Serve cached axis status to many viewers and commands to one operator."""

    def __init__(
        self,
        axes: AxisSet,
        presets: PresetStore,
        transport_errors: tuple[type[Exception], ...] = (OSError,),
        clock: Callable[[], float] = time.monotonic,
        password: str | None = None,
    ) -> None:
        self._axes = axes
        self._password = password
        self._presets = presets
        self._transport_errors = (AxisError, *transport_errors)
        self._clock = clock
        self._lock = threading.Lock()
        self._lease: _Lease | None = None
        self._snapshot: dict[str, dict[str, Any]] = {}
        self._poll_error: str | None = None
        self._shutdown = threading.Event()
        self._poller: threading.Thread | None = None

    def start(self) -> None:
        """Begin refreshing the status cache in the background."""
        self.refresh()
        self._poller = threading.Thread(target=self._poll, name="axis status", daemon=True)
        self._poller.start()

    def stop(self) -> None:
        """Stop polling and de-energise every axis, over a fresh link in case the old one died."""
        self._shutdown.set()
        if self._poller is not None:
            self._poller.join(timeout=2.0)
        self._reconnect()
        failures = []
        for axis in self._axes:
            try:
                axis.set("enable", False)
            except self._transport_errors as error:
                failures.append(f"{axis.name}: {error}")
        if failures:
            raise ControlError("could not disable " + "; ".join(failures))

    def refresh(self) -> None:
        """Read every axis once into the cache."""
        try:
            snapshot = {axis.name: axis.status() for axis in self._axes}
        except self._transport_errors as error:
            with self._lock:
                self._poll_error = str(error)
            self._reconnect()
            return
        with self._lock:
            self._snapshot, self._poll_error = snapshot, None

    def _reconnect(self) -> None:
        """Reopen the transport, so a dropped ADS link heals on a later poll."""
        try:
            self._axes.backend.close()
            self._axes.backend.open()
        except self._transport_errors as error:
            with self._lock:
                self._poll_error = f"reconnect failed: {error}"

    def status(self, token: str | None) -> dict[str, Any]:
        """Return the cached axes plus who holds control."""
        with self._lock:
            lease = self._live_lease()
            return {
                "axes": [
                    {"name": axis.name, "units": axis.config.units.name,
                     "max_velocity": axis.config.limits.velocity,
                     **self._snapshot.get(axis.name, {})}
                    for axis in self._axes
                ],
                "presets": self._presets.names(),
                "error": self._poll_error,
                "controller": lease.holder if lease else None,
                "in_control": lease is not None and token == lease.token,
            }

    def acquire(self, holder: str, token: str | None, password: str | None = None) -> str:
        """Take or renew control, returning the token the holder must present.

        Taking control needs the password when one is set; renewing needs only the token.
        """
        with self._lock:
            lease = self._live_lease()
            if lease is not None and token != lease.token:
                raise ControlError(f"{lease.holder} is in control")
            if lease is not None:
                lease.expires = self._clock() + LEASE_S
                return lease.token
            if self._password is not None and not secrets.compare_digest(
                    (password or "").encode(), self._password.encode()):
                raise ControlError("wrong password")
            self._lease = _Lease(secrets.token_urlsafe(16), holder, self._clock() + LEASE_S)
            return self._lease.token

    def release(self, token: str | None) -> None:
        """Give up control if ``token`` holds it."""
        with self._lock:
            if self._lease is not None and self._lease.token == token:
                self._lease = None

    def command(self, token: str | None, axis_name: str, action: str, **params: float) -> None:
        """Run one operator action on one axis."""
        self._require_control(token)
        axis = self._axes.axis(axis_name)
        try:
            self._run(axis, action, params)
        except self._transport_errors as error:
            raise ControlError(f"{axis_name} {action}: {error}") from error

    @staticmethod
    def _run(axis: Axis, action: str, params: dict[str, float]) -> None:
        match action:
            case "enable":
                axis.enable()
            case "disable":
                axis.disable()
            case "move_relative":
                axis.move_relative(params["distance"], velocity=params["velocity"], wait=False)
            case "move_absolute":
                axis.move_absolute(params["target"], velocity=params["velocity"], wait=False)
            case "reset":
                axis.reset()
            case "home":
                axis.home()
            case "stop":
                axis.stop()
            case _:
                raise ControlError(f"unknown action {action!r}")

    def save_preset(self, token: str | None, name: str) -> None:
        """Store every bar's current position under ``name``."""
        self._require_control(token)
        try:
            bars = {axis.name: SavedBar(axis.position, axis.enabled) for axis in self._axes}
            self._presets.save(name, bars)
        except (PresetError, *self._transport_errors) as error:
            raise ControlError(f"save {name!r}: {error}") from error

    def recall_preset(self, token: str | None, name: str) -> list[str]:
        """Move every enabled bar to its saved target; return the bars left where they are."""
        self._require_control(token)
        try:
            targets = self._presets.get(name)
            moves = self._plan_recall(targets)
            for axis, target in moves:
                axis.move_absolute(target, velocity=axis.config.limits.velocity, wait=False)
        except (PresetError, *self._transport_errors) as error:
            raise ControlError(f"recall {name!r}: {error}") from error
        moving = {axis.name for axis, _ in moves}
        return [axis.name for axis in self._axes if axis.name not in moving]

    def preset(self, name: str) -> dict[str, dict[str, Any]]:
        """Return one save point by bar name, for display."""
        try:
            saved = self._presets.get(name)
        except PresetError as error:
            raise ControlError(str(error)) from error
        return {bar: {"position": entry.position, "enabled": entry.enabled}
                for bar, entry in saved.items()}

    def delete_preset(self, token: str | None, name: str) -> None:
        """Forget a save point."""
        self._require_control(token)
        try:
            self._presets.delete(name)
        except PresetError as error:
            raise ControlError(str(error)) from error

    def _plan_recall(self, saved: Mapping[str, SavedBar]) -> list[tuple[Axis, float]]:
        """Pick the bars to move, refusing the whole recall if any target is out of travel."""
        moves = []
        for axis in self._axes:
            if axis.name not in saved or not axis.enabled:
                continue
            target = saved[axis.name].position
            limits = axis.config.limits
            if not limits.position_is_allowed(target):
                raise ControlError(
                    f"{axis.name} target {target} is outside travel "
                    f"[{limits.min_position}, {limits.max_position}]"
                )
            moves.append((axis, target))
        return moves

    def stop_all(self) -> None:
        """Stop every axis, continuing past failures; open to every viewer on purpose."""
        failures = []
        for axis in self._axes:
            try:
                axis.stop()
            except self._transport_errors as error:
                failures.append(f"{axis.name}: {error}")
        if failures:
            raise ControlError("stop failed for " + "; ".join(failures))

    def _require_control(self, token: str | None) -> None:
        with self._lock:
            lease = self._live_lease()
            if lease is None or token != lease.token:
                raise ControlError("take control first")
            lease.expires = self._clock() + LEASE_S

    def _live_lease(self) -> _Lease | None:
        if self._lease is not None and self._lease.expires < self._clock():
            self._lease = None
        return self._lease

    def _poll(self) -> None:
        while not self._shutdown.wait(_POLL_PERIOD_S):
            self.refresh()
