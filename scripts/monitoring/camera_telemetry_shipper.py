#!/usr/bin/env python3
"""Read Archon telemetry from the lris2_camera libby daemon and write it to InfluxDB 2.x.

Replaces the direct-to-camerad ``archon_collector.py`` on lris2-137: instead of
opening its own connection to camerad, this script reads the ``status_raw``/
``frame_raw`` keywords from the ``camera-interface`` daemon (which owns the one
camerad connection) via libby RPC, then applies the same schema mapping so the
InfluxDB history stays continuous across the cutover.

Schema (one point per scrape, except where multiple channels exist):
  archon_chassis        - global flags, backplane temp, fan tach
  archon_rail           - backplane power rails (P2V5, N6V, USER, ...) with voltage+current
  archon_module_temp    - MOD<n>/TEMP
  archon_hv_bias        - MOD9 HVLC (1..24) and HVHC (1..6) with voltage+current
  archon_xv_bias        - MOD10 XV+/XV- channels (1..4) with voltage+current
  archon_thermal_sensor - MOD11/12 TEMPA/B/C
  archon_heater         - MOD11/12 heater A/B output and PID gains
  archon_dinputs        - MOD11/12 digital input bitmap (raw + per-bit ints)
  archon_vcpu_outreg    - MOD11/12 VCPU output registers 0..15

Credentials come from the standard InfluxDB env vars:
  INFLUXDB_V2_URL, INFLUXDB_V2_TOKEN, INFLUXDB_V2_ORG, INFLUXDB_V2_BUCKET
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, Callable, Dict, Final, Optional

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from libby import Libby
from lris2.driver.camera_interface.cameradclient import CameradClient, StatusValue

DEFAULT_INSTRUMENT: Final[str] = "lris2"
DEFAULT_INTERVAL_S: Final[float] = 60.0
DEFAULT_INFLUX_URL: Final[str] = "http://meridian.caltech.edu:8086"
DEFAULT_RABBITMQ_URL: Final[str] = "amqp://localhost"
DEFAULT_PEER: Final[str] = "lris2_camera"
DEFAULT_SELF_ID: Final[str] = "lris2_camera_shipper"
DEFAULT_RPC_TIMEOUT_S: Final[float] = 5.0

log = logging.getLogger("camera_telemetry_shipper")


# Schema mapping, ported unchanged from archon_collector.py so points keep
# landing in the same measurements/fields as the collector it replaces.

PointSpec = tuple[str, dict[str, str], dict[str, int | float | str]]
Extractor = Callable[[re.Match[str], StatusValue], Optional[PointSpec]]


@dataclass(frozen=True, slots=True)
class MappingRule:
    """One regex-driven rule that turns a STATUS key into a point spec."""

    pattern: re.Pattern[str]
    extract: Extractor


def _as_float(value: StatusValue) -> float:
    return float(value)


def _as_int(value: StatusValue) -> int:
    # InfluxDB rejects mixed int/float on the same field; cast explicitly.
    return int(float(value))


def _hex_to_int(value: StatusValue) -> int:
    """Parse a 64-bit hex string (Archon timestamps) into a signed int64."""
    if isinstance(value, int):
        return value
    return int(str(value), 16)


def _chassis(key: str, kind: str) -> Extractor:
    """Build an extractor that pins one STATUS key into archon_chassis as a single field."""

    def extract(_match: re.Match[str], value: StatusValue) -> PointSpec:
        field_value: int | float = _as_int(value) if kind == "int" else _as_float(value)
        return ("archon_chassis", {}, {key.lower(): field_value})

    return extract


def _rail(match: re.Match[str], value: StatusValue) -> PointSpec:
    rail, suffix = match.group(1), match.group(2)
    field = "voltage" if suffix == "V" else "current"
    return ("archon_rail", {"rail": rail}, {field: _as_float(value)})


def _module_temp(match: re.Match[str], value: StatusValue) -> PointSpec:
    return (
        "archon_module_temp",
        {"module": f"MOD{match.group(1)}"},
        {"temp": _as_float(value)},
    )


def _hv_bias(match: re.Match[str], value: StatusValue) -> PointSpec:
    module, kind, suffix, channel = match.groups()
    field = "voltage" if suffix == "V" else "current"
    return (
        "archon_hv_bias",
        {"module": f"MOD{module}", "kind": kind, "channel": channel},
        {field: _as_float(value)},
    )


def _xv_bias(match: re.Match[str], value: StatusValue) -> PointSpec:
    module, polarity, suffix, channel = match.groups()
    field = "voltage" if suffix == "V" else "current"
    return (
        "archon_xv_bias",
        {"module": f"MOD{module}", "polarity": polarity, "channel": channel},
        {field: _as_float(value)},
    )


def _thermal_sensor(match: re.Match[str], value: StatusValue) -> PointSpec:
    module, sensor = match.groups()
    return (
        "archon_thermal_sensor",
        {"module": f"MOD{module}", "sensor": sensor},
        {"temp": _as_float(value)},
    )


def _heater(match: re.Match[str], value: StatusValue) -> PointSpec:
    module, heater, suffix = match.groups()
    field_map = {"OUTPUT": ("output", _as_float), "P": ("p", _as_int),
                 "I": ("i", _as_int), "D": ("d", _as_int)}
    name, caster = field_map[suffix]
    return (
        "archon_heater",
        {"module": f"MOD{module}", "heater": heater},
        {name: caster(value)},
    )


def _dinputs(match: re.Match[str], value: StatusValue) -> PointSpec:
    raw = str(value)
    fields: dict[str, int | float | str] = {"bits": raw}
    # MSB-first labeling: leftmost char is bit7, rightmost is bit0 (typical convention).
    for index, char in enumerate(reversed(raw)):
        fields[f"bit{index}"] = int(char) if char in "01" else 0
    return ("archon_dinputs", {"module": f"MOD{match.group(1)}"}, fields)


def _vcpu_outreg(match: re.Match[str], value: StatusValue) -> PointSpec:
    module, reg = match.groups()
    return (
        "archon_vcpu_outreg",
        {"module": f"MOD{module}", "reg": reg},
        {"value": _as_int(value)},
    )


def _frame_global_int(key: str) -> Extractor:
    """Extractor for global FRAME ints (RBUF, WBUF)."""

    def extract(_match: re.Match[str], value: StatusValue) -> PointSpec:
        return ("archon_frame_global", {}, {key.lower(): _as_int(value)})

    return extract


def _frame_global_hex(key: str) -> Extractor:
    """Extractor for global FRAME 64-bit hex timestamps (TIMER)."""

    def extract(_match: re.Match[str], value: StatusValue) -> PointSpec:
        return ("archon_frame_global", {}, {key.lower(): _hex_to_int(value)})

    return extract


# Per-buffer FRAME suffix -> (field_name, caster). Hex casters apply to
# Archon timestamp fields (TIMESTAMP and the six edge-timestamp variants).
BUF_FIELD_MAP: Final[dict[str, tuple[str, Callable[[StatusValue], int]]]] = {
    "SAMPLE": ("sample", _as_int),
    "COMPLETE": ("complete", _as_int),
    "MODE": ("mode", _as_int),
    "BASE": ("base", _as_int),
    "FRAME": ("frame", _as_int),
    "WIDTH": ("width", _as_int),
    "HEIGHT": ("height", _as_int),
    "PIXELS": ("pixels", _as_int),
    "LINES": ("lines", _as_int),
    "RAWBLOCKS": ("rawblocks", _as_int),
    "RAWLINES": ("rawlines", _as_int),
    "RAWOFFSET": ("rawoffset", _as_int),
    "TIMESTAMP": ("timestamp", _hex_to_int),
    "RETIMESTAMP": ("re_timestamp", _hex_to_int),
    "FETIMESTAMP": ("fe_timestamp", _hex_to_int),
    "REATIMESTAMP": ("rea_timestamp", _hex_to_int),
    "FEATIMESTAMP": ("fea_timestamp", _hex_to_int),
    "REBTIMESTAMP": ("reb_timestamp", _hex_to_int),
    "FEBTIMESTAMP": ("feb_timestamp", _hex_to_int),
}


def _frame_buffer(match: re.Match[str], value: StatusValue) -> Optional[PointSpec]:
    buffer_idx, suffix = match.group(1), match.group(2)
    entry = BUF_FIELD_MAP.get(suffix)
    if entry is None:
        return None
    field_name, caster = entry
    return (
        "archon_frame_buffer",
        {"buffer": buffer_idx},
        {field_name: caster(value)},
    )


CHASSIS_INT_KEYS: Final[tuple[str, ...]] = (
    "VALID", "COUNT", "LOG", "POWER", "POWERGOOD", "OVERHEAT", "EXTCLKPRESENT",
)
CHASSIS_FLOAT_KEYS: Final[tuple[str, ...]] = ("BACKPLANE_TEMP", "FANTACH")

RULES: Final[tuple[MappingRule, ...]] = (
    *[MappingRule(re.compile(f"^{k}$"), _chassis(k, "int")) for k in CHASSIS_INT_KEYS],
    *[MappingRule(re.compile(f"^{k}$"), _chassis(k, "float")) for k in CHASSIS_FLOAT_KEYS],
    MappingRule(re.compile(r"^MOD(\d+)/(HVLC|HVHC)_([VI])(\d+)$"), _hv_bias),
    MappingRule(re.compile(r"^MOD(\d+)/XV([PN])_([VI])(\d+)$"), _xv_bias),
    MappingRule(re.compile(r"^MOD(\d+)/TEMP([ABC])$"), _thermal_sensor),
    MappingRule(re.compile(r"^MOD(\d+)/HEATER([AB])(OUTPUT|P|I|D)$"), _heater),
    MappingRule(re.compile(r"^MOD(\d+)/DINPUTS$"), _dinputs),
    MappingRule(re.compile(r"^MOD(\d+)/VCPU_OUTREG(\d+)$"), _vcpu_outreg),
    MappingRule(re.compile(r"^MOD(\d+)/TEMP$"), _module_temp),
    # FRAME command fields (Archon frame-buffer state)
    MappingRule(re.compile(r"^TIMER$"), _frame_global_hex("timer")),
    MappingRule(re.compile(r"^RBUF$"), _frame_global_int("rbuf")),
    MappingRule(re.compile(r"^WBUF$"), _frame_global_int("wbuf")),
    MappingRule(re.compile(r"^BUF(\d)([A-Z]+)$"), _frame_buffer),
    # Catch-all power rail rule. Must be LAST so chassis exact matches win.
    MappingRule(re.compile(r"^([A-Z][A-Z0-9]+)_([VI])$"), _rail),
)


# Warn once per unknown key, not per scrape.
_unknown_keys_warned: set[str] = set()


def _classify(key: str, value: StatusValue) -> Optional[PointSpec]:
    matched_but_dropped = False
    for rule in RULES:
        match = rule.pattern.match(key)
        if match:
            result = rule.extract(match, value)
            if result is not None:
                return result
            matched_but_dropped = True
    if key not in _unknown_keys_warned:
        kind = "unknown suffix" if matched_but_dropped else "unknown key"
        log.warning("STATUS/FRAME %s dropped: %s=%r", kind, key, value)
        _unknown_keys_warned.add(key)
    return None


def build_points(
    status: Dict[str, StatusValue],
    instrument: str,
    timestamp: datetime,
) -> list[Point]:
    """Convert a parsed STATUS/FRAME dict into a list of InfluxDB points.

    Multiple input keys that target the same (measurement, tags) - e.g. the
    voltage and current of one HV bias channel - are merged into a single Point.
    """
    # Key = (measurement, frozenset of tag items)
    grouped: dict[tuple[str, frozenset[tuple[str, str]]], dict[str, int | float | str]] = {}
    tag_lookup: dict[tuple[str, frozenset[tuple[str, str]]], dict[str, str]] = {}

    for key, value in status.items():
        spec = _classify(key, value)
        if spec is None:
            continue
        measurement, tags, fields = spec
        group_key = (measurement, frozenset(tags.items()))
        grouped.setdefault(group_key, {}).update(fields)
        tag_lookup.setdefault(group_key, tags)

    points: list[Point] = []
    for group_key, fields in grouped.items():
        measurement, _ = group_key
        point = Point(measurement).tag("instrument", instrument).time(
            timestamp, write_precision=WritePrecision.S
        )
        for tag_name, tag_value in tag_lookup[group_key].items():
            point = point.tag(tag_name, tag_value)
        for field_name, field_value in fields.items():
            point = point.field(field_name, field_value)
        points.append(point)

    return points


class ConfigError(RuntimeError):
    """Raised when InfluxDB configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class InfluxConfig:
    """Connection parameters for an InfluxDB 2.x bucket."""

    url: str
    token: str
    org: str
    bucket: str

    @classmethod
    def from_env(cls) -> InfluxConfig:
        try:
            return cls(
                url=os.environ.get("INFLUXDB_V2_URL", DEFAULT_INFLUX_URL),
                token=os.environ["INFLUXDB_V2_TOKEN"],
                org=os.environ["INFLUXDB_V2_ORG"],
                bucket=os.environ["INFLUXDB_V2_BUCKET"],
            )
        except KeyError as missing:
            raise ConfigError(
                f"missing required env var: {missing.args[0]} "
                "(need INFLUXDB_V2_TOKEN, INFLUXDB_V2_ORG, INFLUXDB_V2_BUCKET)"
            ) from missing


class InfluxWriter:
    """Context-managed wrapper around `InfluxDBClient` for synchronous writes."""

    def __init__(self, config: InfluxConfig) -> None:
        self._config = config
        self._client: Optional[InfluxDBClient] = None
        self._write_api = None

    def __enter__(self) -> InfluxWriter:
        self._client = InfluxDBClient(
            url=self._config.url, token=self._config.token, org=self._config.org
        )
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
        self._write_api = None

    def write(self, points: list[Point]) -> None:
        if self._write_api is None:
            raise RuntimeError("InfluxWriter used outside its context manager")
        self._write_api.write(bucket=self._config.bucket, record=points)


class TelemetryReadError(RuntimeError):
    """Raised when a keyword read from the camera-interface daemon fails."""


def _unwrap(result: Any) -> Dict[str, Any]:
    """Some transports wrap the keyword response in {"resp": {...}}; unwrap it."""
    return result.get("resp", result) if isinstance(result, dict) else {}


def read_telemetry(lib: Libby, peer: str, timeout_s: float) -> Dict[str, StatusValue]:
    """Read status_raw + frame_raw from the daemon and parse them.

    Reuses CameradClient._parse_reply (the same coercion the daemon itself
    used to build its cache) instead of re-implementing it a third time.
    """
    merged: Dict[str, StatusValue] = {}
    for keyword in ("status_raw", "frame_raw"):
        result = lib.rpc(peer, keyword, {}, ttl_ms=int(timeout_s * 1000))
        resp = _unwrap(result)
        if not resp.get("ok", False):
            raise TelemetryReadError(f"{keyword}: {resp.get('error', 'unknown error')}")
        merged.update(CameradClient._parse_reply(resp.get("value") or ""))
    return merged


_shutdown_requested = False


def _handle_signal(signum: int, _frame: object) -> None:
    global _shutdown_requested
    log.info("received signal %s, shutting down after current scrape",
              signal.Signals(signum).name)
    _shutdown_requested = True


def run(
    lib: Libby,
    peer: str,
    writer: Optional[InfluxWriter],
    *,
    instrument: str,
    interval_s: float,
    rpc_timeout_s: float,
) -> None:
    """Run the read-and-write loop until shutdown is requested."""
    next_scrape = time.monotonic()
    while not _shutdown_requested:
        timestamp = datetime.now(tz=timezone.utc)
        try:
            telemetry = read_telemetry(lib, peer, rpc_timeout_s)
            points = build_points(telemetry, instrument=instrument, timestamp=timestamp)
        except TelemetryReadError as exc:
            log.error("scrape failed: %s", exc)
        else:
            if writer is None:
                log.info("dry-run: %d points (showing first 3)", len(points))
                for point in points[:3]:
                    log.info("  %s", point.to_line_protocol())
            else:
                try:
                    writer.write(points)
                except Exception as exc:  # pylint: disable=broad-except
                    log.error("influx write failed: %s", exc)
                else:
                    log.info("wrote %d points", len(points))

        next_scrape += interval_s
        sleep_for = next_scrape - time.monotonic()
        if sleep_for > 0 and not _shutdown_requested:
            time.sleep(sleep_for)
        else:
            # Fell behind schedule; resync rather than burning CPU.
            next_scrape = time.monotonic()


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point for the shipper."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--peer", default=DEFAULT_PEER,
                        help="camera-interface daemon's peer_id (default: %(default)s)")
    parser.add_argument("--self-id", default=DEFAULT_SELF_ID)
    parser.add_argument("--rabbitmq-url", default=DEFAULT_RABBITMQ_URL)
    parser.add_argument("--instrument", default=DEFAULT_INSTRUMENT)
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_S,
                        help="seconds between scrapes (default: 60)")
    parser.add_argument("--rpc-timeout", type=float, default=DEFAULT_RPC_TIMEOUT_S)
    parser.add_argument("--once", action="store_true", help="poll once and exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="don't connect to InfluxDB; just print line protocol")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    if args.dry_run:
        config = None
    else:
        try:
            config = InfluxConfig.from_env()
        except ConfigError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

    lib = Libby.rabbitmq(self_id=args.self_id, rabbitmq_url=args.rabbitmq_url, keys=[])
    try:
        if args.once:
            timestamp = datetime.now(tz=timezone.utc)
            try:
                telemetry = read_telemetry(lib, args.peer, args.rpc_timeout)
                points = build_points(telemetry, args.instrument, timestamp)
            except TelemetryReadError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 1

            if config is None:
                for point in points:
                    print(point.to_line_protocol())
                print(f"\n{len(points)} points (dry-run)", file=sys.stderr)
                return 0

            with InfluxWriter(config) as writer:
                writer.write(points)
            log.info("wrote %d points", len(points))
            return 0

        if config is None:
            run(lib, args.peer, None, instrument=args.instrument,
                interval_s=args.interval, rpc_timeout_s=args.rpc_timeout)
            return 0

        with InfluxWriter(config) as writer:
            run(lib, args.peer, writer, instrument=args.instrument,
                interval_s=args.interval, rpc_timeout_s=args.rpc_timeout)
        return 0
    finally:
        lib.stop()


if __name__ == "__main__":
    sys.exit(main())
