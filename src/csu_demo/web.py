"""Flask routes for the CSU demo page, its JSON API and the webcam stream."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Final

from cooethercat import AxisError
from flask import Flask, Response, jsonify, render_template, request

from .camera import SharedCamera
from .control import LEASE_S, ControlError, Controller
from .layout import Layout

TOKEN_COOKIE: Final = "csu_control"
_BOUNDARY: Final = "frame"
_NUMBER_PARAMS: Final = ("distance", "target", "velocity")


def create_app(controller: Controller, camera: SharedCamera | None, layout: Layout) -> Flask:
    """Build the demo app around an already started controller."""
    app = Flask(__name__)

    @app.get("/")
    def index() -> str:
        return render_template("index.html", has_camera=camera is not None, lease_s=LEASE_S)

    @app.get("/api/layout")
    def show_layout() -> Response:
        return jsonify(
            rows=layout.rows,
            bars={bar: {"side": slot.side, "row": slot.row, "plus": slot.plus}
                  for bar, slot in layout.slots.items()},
        )

    @app.get("/api/status")
    def status() -> Response:
        return jsonify(controller.status(request.cookies.get(TOKEN_COOKIE)))

    @app.post("/api/control")
    def take_control() -> Response | tuple[Response, int]:
        body = request.get_json(silent=True) or {}
        holder = str(request.remote_addr or "unknown")
        try:
            token = controller.acquire(holder, request.cookies.get(TOKEN_COOKIE),
                                       body.get("password"))
        except ControlError as error:
            return jsonify(error=str(error)), 409
        response = jsonify(ok=True)
        response.set_cookie(TOKEN_COOKIE, token, httponly=True, samesite="Strict")
        return response

    @app.delete("/api/control")
    def release_control() -> Response:
        controller.release(request.cookies.get(TOKEN_COOKIE))
        response = jsonify(ok=True)
        response.delete_cookie(TOKEN_COOKIE)
        return response

    @app.post("/api/axes/<name>/<action>")
    def command(name: str, action: str) -> Response | tuple[Response, int]:
        try:
            params = _numbers(request.get_json(silent=True) or {})
            controller.command(request.cookies.get(TOKEN_COOKIE), name, action, **params)
        except (ControlError, AxisError, KeyError, ValueError) as error:
            return jsonify(error=str(error)), 400
        return jsonify(ok=True)

    @app.post("/api/presets")
    def save_preset() -> Response | tuple[Response, int]:
        name = str((request.get_json(silent=True) or {}).get("name", ""))
        try:
            controller.save_preset(request.cookies.get(TOKEN_COOKIE), name)
        except ControlError as error:
            return jsonify(error=str(error)), 400
        return jsonify(ok=True)

    @app.get("/api/presets/<name>")
    def show_preset(name: str) -> Response | tuple[Response, int]:
        try:
            return jsonify(controller.preset(name))
        except ControlError as error:
            return jsonify(error=str(error)), 404

    @app.post("/api/presets/<name>/recall")
    def recall_preset(name: str) -> Response | tuple[Response, int]:
        try:
            skipped = controller.recall_preset(request.cookies.get(TOKEN_COOKIE), name)
        except ControlError as error:
            return jsonify(error=str(error)), 400
        return jsonify(ok=True, skipped=skipped)

    @app.delete("/api/presets/<name>")
    def delete_preset(name: str) -> Response | tuple[Response, int]:
        try:
            controller.delete_preset(request.cookies.get(TOKEN_COOKIE), name)
        except ControlError as error:
            return jsonify(error=str(error)), 400
        return jsonify(ok=True)

    @app.post("/api/stop")
    def stop_all() -> Response | tuple[Response, int]:
        try:
            controller.stop_all()
        except ControlError as error:
            return jsonify(error=str(error)), 502
        return jsonify(ok=True)

    @app.get("/stream.mjpg")
    def stream() -> Response | tuple[str, int]:
        if camera is None:
            return "no camera configured", 404
        return Response(
            _multipart(camera.frames()),
            mimetype=f"multipart/x-mixed-replace; boundary={_BOUNDARY}",
        )

    return app


def _numbers(body: dict[str, Any]) -> dict[str, float]:
    return {key: float(body[key]) for key in _NUMBER_PARAMS if key in body}


def _multipart(frames: Iterator[bytes]) -> Iterator[bytes]:
    for frame in frames:
        yield (
            f"--{_BOUNDARY}\r\nContent-Type: image/jpeg\r\n"
            f"Content-Length: {len(frame)}\r\n\r\n"
        ).encode() + frame + b"\r\n"
