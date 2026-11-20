"""CSU bar keywords: per-bar motion and drive telemetry, translated into axis commands."""
import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, Protocol

from cooethercat import STATUS, Axis, AxisError, AxisSet, CoeType

# Errors a keyword turns into a libby error reply instead of crashing the daemon
TransportErrors = tuple[type[Exception], ...]


class Registry(Protocol):
    """The slice of libby's KeywordRegistry used here."""

    def bool(self, name: str, **options: Any) -> Any:
        """Register a bool keyword."""

    def int(self, name: str, **options: Any) -> Any:
        """Register an int keyword."""

    def float(self, name: str, **options: Any) -> Any:
        """Register a float keyword."""

    def string(self, name: str, **options: Any) -> Any:
        """Register a string keyword."""

    def trigger(self, name: str, **options: Any) -> Any:
        """Register a trigger keyword."""


@dataclass(frozen=True)
class Telemetry:
    """One EPOS4 object served as a read-only keyword."""

    keyword: str
    index: int
    subindex: int
    kind: CoeType
    scale: float
    units: str
    description: str


# EPOS4 objects; the motors have no temperature sensor, so motor I2t stands in for winding heat
TELEMETRY: Final = (
    Telemetry("boardtemp", 0x3201, 1, CoeType.INT16, 0.1, "C", "Drive power stage temperature"),
    Telemetry("i2tmotor", 0x3200, 1, CoeType.UINT16, 1.0, "%",
              "Drive thermal model of the motor winding"),
    Telemetry("i2tstage", 0x3200, 2, CoeType.UINT16, 1.0, "%",
              "Drive thermal model of the power stage"),
    Telemetry("current", 0x30D1, 1, CoeType.INT32, 1.0, "mA", "Motor current, averaged"),
    Telemetry("supply", 0x2200, 1, CoeType.UINT16, 0.1, "V", "Drive supply voltage"),
)


# The readings the browser demo charts per bar
_CHARTED: Final = tuple(item for item in TELEMETRY if item.keyword in ("boardtemp", "current"))


# How old a reading a keyword may answer with, so a dump of every keyword reads the PLC and
# each drive object once; coo-ethercat drops cached readings on any write
MAX_AGE_S: Final = 0.5
# Every bar's PLC readbacks plus its profile velocity, read for all bars in one sum request
SNAPSHOT_FIELDS: Final = (*STATUS, "velocity")


def bar_number(axis: Axis) -> int:
    """Return N for a bar named CSU-N, the suffix of its keywords."""
    return int(axis.name.rsplit("-", 1)[1])


class CsuKeywords:
    """Translate keyword reads and writes into axis commands and drive reads."""

    def __init__(self, axes: AxisSet, transport_errors: TransportErrors = (OSError,),
                 online: Callable[[], bool] = lambda: True) -> None:
        self._axes = axes
        self._online = online
        self._errors = (AxisError, *transport_errors)
        self._locks = {axis.name: threading.Lock() for axis in axes}

    def register(self, registry: Registry) -> None:
        """Register every bar's keywords plus the CSU-wide ones."""
        for axis in self._axes:
            self._register_bar(registry, axis)
        registry.bool("ismoving", getter=self._guard(self.any_moving),
                      description="Any bar is moving")
        registry.trigger("halt", action=self._guard(self.halt_all),
                         description="Stop every bar, continuing past failures")
        registry.string("status", getter=self._guard(self.status_json),
                        description="Every bar's readbacks as JSON, keyed by bar name")
        registry.string("telemetry", getter=self._guard(self.telemetry_json),
                        description="Every bar's board temperature (C) and current (mA) as JSON")

    def _register_bar(self, registry: Registry, axis: Axis) -> None:
        n, units = bar_number(axis), axis.config.units.name

        def field(name: str) -> Any:
            return self.snapshot()[axis.name][name]

        registry.float(f"positionvalue{n}", units=units,
                       getter=self._guard(lambda: round(float(field("position")), 4)),
                       setter=self._guard(lambda target: self.move_to(axis, float(target))),
                       description=f"{axis.name} position; a write is an absolute move")
        registry.float(f"velocity{n}", units=f"{units}/s",
                       getter=self._guard(lambda: float(field("velocity"))),
                       setter=self._guard(lambda value: self.set_velocity(axis, float(value))),
                       description=f"{axis.name} profile velocity for moves")
        registry.bool(f"ismoving{n}", getter=self._guard(lambda: bool(field("moving"))),
                      description=f"{axis.name} is moving")
        registry.bool(f"isenabled{n}", getter=self._guard(lambda: bool(field("enabled"))),
                      setter=self._guard(lambda on: self.set_enabled(axis, bool(on))),
                      description=f"{axis.name} drive is energised; write to switch")
        registry.int(f"error{n}",
                     getter=self._guard(lambda: int(field("error_id")) if field("error") else 0),
                     description=f"{axis.name} latched fault id, 0 when clear")
        registry.trigger(f"halt{n}", action=self._guard(axis.stop),
                         description=f"Stop {axis.name}")
        registry.trigger(f"reset{n}", action=self._guard(axis.reset),
                         description=f"Clear a latched fault on {axis.name}")
        for item in TELEMETRY:
            registry.float(f"{item.keyword}{n}", units=item.units,
                           getter=self._guard(lambda item=item: self.read_telemetry(axis, item)),
                           description=f"{axis.name}: {item.description}")

    def move_to(self, axis: Axis, target: float) -> None:
        """Start an absolute move, refusing while the bar is already moving."""
        with self._locks[axis.name]:
            if axis.moving:
                raise AxisError(f"{axis.name} is already moving")
            # A bar never given a velocity holds 0, which the PLC would fault on
            velocity = float(axis.get("velocity")) or axis.config.limits.velocity
            axis.move_absolute(target, velocity=velocity, wait=False)

    def set_velocity(self, axis: Axis, value: float) -> None:
        """Set the profile velocity used by later moves, within the bar's limit."""
        limit = axis.config.limits.velocity
        if not 0 < value <= limit:
            raise AxisError(f"{axis.name} velocity must be in (0, {limit}]")
        axis.set("velocity", value)

    def set_enabled(self, axis: Axis, on: bool) -> None:
        """Energise or de-energise a bar's drive and wait for it to follow."""
        with self._locks[axis.name]:
            if on:
                axis.enable()
            else:
                axis.disable()

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Return every bar's PLC readbacks, reading the PLC at most once per MAX_AGE_S."""
        return self._axes.read(SNAPSHOT_FIELDS, max_age=MAX_AGE_S)

    def read_telemetry(self, axis: Axis, item: Telemetry) -> float:
        """Read one drive object, at most once per MAX_AGE_S, scaled to engineering units."""
        raw = axis.read_object(item.index, item.subindex, item.kind, max_age=MAX_AGE_S)
        return round(float(raw) * item.scale, 2)

    def status_json(self) -> str:
        """Return every bar's status snapshot as one JSON object."""
        return json.dumps({name: {field: fields[field] for field in STATUS}
                           for name, fields in self.snapshot().items()})

    def telemetry_json(self) -> str:
        """Return every bar's board temperature and current, null where a drive fails to answer."""
        readings: dict[str, dict[str, float | None]] = {}
        for axis in self._axes:
            values: dict[str, float | None] = {}
            for item in _CHARTED:
                try:
                    values[item.keyword] = self.read_telemetry(axis, item)
                except self._errors:
                    values[item.keyword] = None
            readings[axis.name] = values
        return json.dumps(readings)

    def any_moving(self) -> bool:
        """Return whether any bar is moving, read fresh since shutdown relies on it."""
        return any(fields["moving"] for fields in self._axes.read(("moving",)).values())

    def halt_all(self) -> None:
        """Stop every bar, raising afterwards if any of them could not be told to."""
        failures = []
        for axis in self._axes:
            try:
                axis.stop()
            except self._errors as error:
                failures.append(f"{axis.name}: {error}")
        if failures:
            raise RuntimeError("halt failed for " + "; ".join(failures))

    def _guard(self, call: Callable[..., Any]) -> Callable[..., Any]:
        """Report axis and transport failures as RuntimeError, which libby replies with."""
        def guarded(*args: Any) -> Any:
            # Fail fast while the link is down, so a reader of every keyword is not held up
            if not self._online():
                raise RuntimeError("PLC unreachable")
            try:
                return call(*args)
            except self._errors as error:
                raise RuntimeError(str(error)) from error
        return guarded
