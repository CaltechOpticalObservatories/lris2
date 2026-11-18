"""Serve the CSU demo page: ``lris2-csu-demo --config config/csu/csu.yaml``."""

from __future__ import annotations

import argparse
import dataclasses
import os
import shlex
import signal
import sys
from pathlib import Path

import waitress
import yaml
from cooethercat import Axis, AxisSet
from cooethercat.backends.sim import open_simulated
from cooethercat.config import Backend, TopologyConfig, parse_topology
from libby import Client
from libby.errors import LibbyError

from lris2.daemon import broker_url

from .camera import CommandSource, SharedCamera, StreamFormat, gstreamer_argv
from .control import Controller
from .history import POLL_S, Poller, TelemetryHistory, record_telemetry
from .layout import Layout, load_layout
from .libby_backend import LibbyBackend
from .power import PowerPanel
from .presets import PresetStore
from .web import create_app

# Each open MJPEG stream holds a worker thread for as long as it is watched
_SERVER_THREADS = 16
PASSWORD_ENV = "LRIS2_CSU_DEMO_PASSWORD"
# A daemon that is down or refuses a request; the page reports it and keeps polling
_ERRORS: tuple[type[Exception], ...] = (OSError, LibbyError)


def main() -> None:
    """Run the demo server until interrupted, then disable every axis."""
    # systemd and kill stop with SIGTERM; route it through the cleanup below
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    args = _parse_args()
    topology = _topology(args)
    layout = load_layout(args.layout) if args.layout else Layout(rows=12, slots={})
    camera = None if args.no_camera else SharedCamera(lambda: CommandSource(_capture_argv(args)))
    client = None if args.sim else Client.rabbitmq(self_id="csu-demo", rabbitmq_url=broker_url())
    history = TelemetryHistory()
    power = None if client is None or args.no_power else PowerPanel(client, args.pdu)
    pollers = _pollers(client, args, history, power)
    with _open_axes(topology, args, client) as axes:
        controller = Controller(
            axes, PresetStore(args.presets), transport_errors=_ERRORS,
            password=os.environ.get(PASSWORD_ENV) or None,
        )
        controller.start()
        for poller in pollers:
            poller.start()
        try:
            app = create_app(controller, camera, layout, history=history, power=power,
                             power_errors=_ERRORS)
            waitress.serve(app, host=args.host, port=args.port, threads=_SERVER_THREADS)
        finally:
            for poller in pollers:
                poller.stop()
            controller.stop()


def _pollers(client: Client | None, args: argparse.Namespace, history: TelemetryHistory,
             power: PowerPanel | None) -> list[Poller]:
    if client is None:
        return []
    pollers = [Poller("telemetry", POLL_S,
                      record_telemetry(lambda: client.get(f"{args.peer}.telemetry"), history),
                      _ERRORS + (ValueError,))]
    if power is not None:
        def refresh_power() -> None:
            try:
                power.refresh()
            except _ERRORS as error:
                power.fail(error)
                raise
        pollers.append(Poller("power", POLL_S, refresh_power, _ERRORS))
    return pollers


def _capture_argv(args: argparse.Namespace) -> list[str]:
    stream = StreamFormat(args.width, args.height, args.fps, args.quality)
    argv = gstreamer_argv(args.camera, stream)
    return argv if args.camera_host is None else ["ssh", args.camera_host, shlex.join(argv)]


def _topology(args: argparse.Namespace) -> TopologyConfig:
    # The daemon's own config, so limits and units match what it enforces
    with args.config.open(encoding="utf-8") as handle:
        topology = parse_topology(yaml.safe_load(handle)["topology"], source=str(args.config))
    return dataclasses.replace(topology, backend=Backend.SIM) if args.sim else topology


def _open_axes(topology: TopologyConfig, args: argparse.Namespace,
               client: Client | None) -> AxisSet:
    if client is None:
        return open_simulated(topology)
    backend = LibbyBackend(client, args.peer)
    axes = AxisSet(backend,
                   {config.keyword_name: Axis(backend, config) for config in topology.axes})
    backend.open()
    return axes


def _default_presets_path() -> Path:
    # systemd's StateDirectory= sets STATE_DIRECTORY; outside it use the XDG state dir
    state = os.environ.get("STATE_DIRECTORY") or Path.home() / ".local/state/lris2"
    return Path(state) / "csu-presets.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True,
                        help="CSU daemon config listing the bars, e.g. config/csu/csu.yaml")
    parser.add_argument("--sim", action="store_true", help="simulate the axes, no daemon")
    parser.add_argument("--peer", default="lris2.csu", help="CSU daemon to drive the bars through")
    parser.add_argument("--pdu", default="l2power.pdu-ethercat", help="PDU daemon feeding the CSU")
    parser.add_argument("--no-power", action="store_true", help="hide the PDU panel")
    parser.add_argument("--camera", default="/dev/video0", help="V4L2 device")
    parser.add_argument("--camera-host", help="capture on this SSH host instead of locally")
    parser.add_argument("--width", type=int, default=StreamFormat.width)
    parser.add_argument("--height", type=int, default=StreamFormat.height)
    parser.add_argument("--fps", type=int, default=StreamFormat.fps)
    parser.add_argument("--quality", type=int, default=StreamFormat.quality,
                        help="JPEG quality 1-100")
    parser.add_argument("--no-camera", action="store_true")
    parser.add_argument("--layout", type=Path,
                        help="bar slots on the CSU, e.g. config/csu/layout.yaml")
    parser.add_argument("--presets", type=Path, default=_default_presets_path(),
                        help="JSON file holding the save points")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    return parser.parse_args()


if __name__ == "__main__":
    main()
