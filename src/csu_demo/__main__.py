"""Serve the CSU demo page: ``lris2-csu-demo --config csu-demo.yaml``."""

from __future__ import annotations

import argparse
import dataclasses
import os
import shlex
import signal
import sys
from pathlib import Path

import pyads
import waitress
from cooethercat.backends.sim import open_simulated
from cooethercat.backends.twincat import open_twincat
from cooethercat.config import Backend, TopologyConfig, TwincatTransport, load_topology

from .camera import CommandSource, SharedCamera, StreamFormat, gstreamer_argv
from .control import Controller
from .layout import Layout, load_layout
from .presets import PresetStore
from .web import create_app

# Each open MJPEG stream holds a worker thread for as long as it is watched
_SERVER_THREADS = 16


def main() -> None:
    """Run the demo server until interrupted, then disable every axis."""
    # systemd and kill stop with SIGTERM; route it through the cleanup below
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    args = _parse_args()
    topology = _topology(args)
    layout = load_layout(args.layout) if args.layout else Layout(rows=12, slots={})
    axes = open_simulated(topology) if args.sim else open_twincat(topology)
    camera = None if args.no_camera else SharedCamera(lambda: CommandSource(_capture_argv(args)))
    with axes:
        controller = Controller(
            axes, PresetStore(args.presets), transport_errors=(OSError, pyads.ADSError)
        )
        controller.start()
        try:
            waitress.serve(create_app(controller, camera, layout), host=args.host, port=args.port,
                           threads=_SERVER_THREADS)
        finally:
            controller.stop()


def _capture_argv(args: argparse.Namespace) -> list[str]:
    stream = StreamFormat(args.width, args.height, args.fps, args.quality)
    argv = gstreamer_argv(args.camera, stream)
    return argv if args.camera_host is None else ["ssh", args.camera_host, shlex.join(argv)]


def _topology(args: argparse.Namespace) -> TopologyConfig:
    topology = load_topology(args.config)
    if args.sim:
        return dataclasses.replace(topology, backend=Backend.SIM)
    transport = topology.transport
    if not isinstance(transport, TwincatTransport):
        raise SystemExit(f"{args.config} is not a TwinCAT topology; use --sim")
    overrides = {
        key: value for key, value in (("host", args.plc_host), ("local_net_id", args.local_net_id))
        if value is not None
    }
    return dataclasses.replace(topology, transport=dataclasses.replace(transport, **overrides))


def _default_presets_path() -> Path:
    # systemd's StateDirectory= sets STATE_DIRECTORY; outside it use the XDG state dir
    state = os.environ.get("STATE_DIRECTORY") or Path.home() / ".local/state/lris2"
    return Path(state) / "csu-presets.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="coo-ethercat topology YAML")
    parser.add_argument("--sim", action="store_true", help="simulate the axes, no PLC")
    parser.add_argument("--plc-host", help="override the PLC address, e.g. 127.0.0.1 via a tunnel")
    parser.add_argument("--local-net-id", help="override this host's AMS net id")
    parser.add_argument("--camera", default="/dev/video0", help="V4L2 device")
    parser.add_argument("--camera-host", help="capture on this SSH host instead of locally")
    parser.add_argument("--width", type=int, default=StreamFormat.width)
    parser.add_argument("--height", type=int, default=StreamFormat.height)
    parser.add_argument("--fps", type=int, default=StreamFormat.fps)
    parser.add_argument("--quality", type=int, default=StreamFormat.quality, help="JPEG quality 1-100")
    parser.add_argument("--no-camera", action="store_true")
    parser.add_argument("--layout", type=Path, help="bar slots on the CSU, e.g. config/csu/layout.yaml")
    parser.add_argument("--presets", type=Path, default=_default_presets_path(),
                        help="JSON file holding the save points")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    return parser.parse_args()


if __name__ == "__main__":
    main()
