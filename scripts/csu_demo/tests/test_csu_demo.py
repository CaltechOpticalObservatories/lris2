"""Tests for the CSU browser demo against simulated axes and a fake camera."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar

import pytest
from cooethercat import AxisSet
from cooethercat.backends.sim import open_simulated
from cooethercat.config import parse_topology
from flask.testing import FlaskClient
from csu_demo.camera import SharedCamera
from csu_demo.control import LEASE_S, Controller
from csu_demo.layout import Layout, LayoutError, Side, Slot, load_layout
from csu_demo.presets import PresetStore, SavedBar
from csu_demo.web import TOKEN_COOKIE, create_app

TOPOLOGY: dict[str, Any] = {
    "name": "csu-sim",
    "backend": "sim",
    "transport": {"tick_s": 0.002},
    "defaults": {
        "units": {"name": "mm"},
        "limits": {"velocity": 50.0, "min_position": -20.0, "max_position": 20.0},
    },
    "axes": [{"name": "CSU-0"}, {"name": "CSU-1"}],
}
JPEG = b"\xff\xd8fake-frame\xff\xd9"
LAYOUT = Layout(rows=12, slots={"CSU-0": Slot(Side.LEFT, 7, Side.LEFT)})
REPO_LAYOUT = Path(__file__).parents[3] / "config" / "csu" / "csu.yaml"


class FakeSource:
    """Endless stream of identical JPEG frames."""

    instances: ClassVar[list[FakeSource]] = []

    def __init__(self) -> None:
        self.closed = threading.Event()
        FakeSource.instances.append(self)

    def read(self, size: int) -> bytes:
        if self.closed.wait(0.01):
            return b""
        return JPEG

    def close(self) -> None:
        self.closed.set()


class FakeClock:
    """Manually advanced monotonic clock."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture(name="clock")
def clock_fixture() -> FakeClock:
    return FakeClock()


@pytest.fixture(name="presets_path")
def presets_path_fixture(tmp_path: Path) -> Path:
    return tmp_path / "presets.json"


@pytest.fixture(name="axes")
def axes_fixture() -> Iterator[AxisSet]:
    with open_simulated(parse_topology(TOPOLOGY)) as axes:
        yield axes


@pytest.fixture(name="controller")
def controller_fixture(axes: AxisSet, clock: FakeClock, presets_path: Path) -> Controller:
    controller = Controller(axes, PresetStore(presets_path), clock=clock)
    controller.refresh()
    return controller


@pytest.fixture(name="camera")
def camera_fixture() -> SharedCamera:
    FakeSource.instances.clear()
    return SharedCamera(FakeSource)


@pytest.fixture(name="client")
def client_fixture(controller: Controller, camera: SharedCamera) -> FlaskClient:
    return create_app(controller, camera, LAYOUT).test_client()


def _take_control(client: FlaskClient) -> None:
    assert client.post("/api/control", json={}).status_code == 200


def _position(client: FlaskClient, controller: Controller, name: str) -> float:
    controller.refresh()
    axes = client.get("/api/status").get_json()["axes"]
    return float(next(axis["position"] for axis in axes if axis["name"] == name))


def _wait_for(predicate: Any, timeout_s: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not predicate():
        assert time.monotonic() < deadline, "condition not reached"
        time.sleep(0.01)


def test_index_serves_page_with_stream(client: FlaskClient) -> None:
    page = client.get("/").get_data(as_text=True)
    assert "stream.mjpg" in page


def test_status_lists_every_axis(client: FlaskClient) -> None:
    status = client.get("/api/status").get_json()
    assert [axis["name"] for axis in status["axes"]] == ["CSU-0", "CSU-1"]
    assert status["axes"][0]["units"] == "mm"
    assert status["controller"] is None


def test_commands_need_control(client: FlaskClient) -> None:
    response = client.post("/api/axes/CSU-0/enable", json={})
    assert response.status_code == 400
    assert "take control" in response.get_json()["error"]


def test_operator_enables_and_moves(client: FlaskClient, controller: Controller) -> None:
    _take_control(client)
    assert client.post("/api/axes/CSU-0/enable", json={}).status_code == 200
    response = client.post("/api/axes/CSU-0/move_relative", json={"distance": 5, "velocity": 40})
    assert response.status_code == 200

    def landed() -> bool:
        controller.refresh()
        axis = client.get("/api/status").get_json()["axes"][0]
        return not axis["moving"] and axis["position"] == pytest.approx(5.0)

    _wait_for(landed)


def test_move_outside_travel_is_refused(client: FlaskClient) -> None:
    _take_control(client)
    client.post("/api/axes/CSU-0/enable", json={})
    response = client.post("/api/axes/CSU-0/move_relative", json={"distance": 30, "velocity": 5})
    assert response.status_code == 400
    assert "travel" in response.get_json()["error"]


def test_second_operator_is_refused_until_lease_expires(
    client: FlaskClient, controller: Controller, clock: FakeClock
) -> None:
    _take_control(client)
    other = create_app(controller, None, LAYOUT).test_client()
    other.environ_base["REMOTE_ADDR"] = "10.1.1.20"
    assert other.post("/api/control", json={}).status_code == 409
    clock.now += LEASE_S + 1
    assert other.post("/api/control", json={}).status_code == 200
    assert other.get("/api/status").get_json()["controller"] == "10.1.1.20"


def test_holder_is_shown_by_address(client: FlaskClient) -> None:
    _take_control(client)
    assert client.post("/api/control", json={}).status_code == 200
    assert client.get("/api/status").get_json()["controller"] == "127.0.0.1"


def test_release_clears_control(client: FlaskClient) -> None:
    _take_control(client)
    client.delete("/api/control")
    status = client.get("/api/status").get_json()
    assert status["controller"] is None
    assert client.get_cookie(TOKEN_COOKIE) is None


def test_plc_error_during_command_is_reported_as_json(
    client: FlaskClient, controller: Controller, monkeypatch: pytest.MonkeyPatch
) -> None:
    _take_control(client)

    def broken_link(*_: Any) -> None:
        raise OSError("ADS link lost")

    monkeypatch.setattr(controller, "_run", broken_link)
    response = client.post("/api/axes/CSU-0/enable", json={})
    assert response.status_code == 400
    assert "ADS link lost" in response.get_json()["error"]


def test_save_point_round_trip(client: FlaskClient, controller: Controller) -> None:
    _take_control(client)
    for bar in ("CSU-0", "CSU-1"):
        client.post(f"/api/axes/{bar}/enable", json={})
    client.post("/api/axes/CSU-0/move_relative", json={"distance": 4, "velocity": 40})
    _wait_for(lambda: _position(client, controller, "CSU-0") == pytest.approx(4.0))

    assert client.post("/api/presets", json={"name": "open"}).status_code == 200
    assert client.get("/api/status").get_json()["presets"] == ["open"]

    client.post("/api/axes/CSU-0/move_relative", json={"distance": -9, "velocity": 40})
    client.post("/api/axes/CSU-1/move_relative", json={"distance": 6, "velocity": 40})
    _wait_for(lambda: _position(client, controller, "CSU-1") == pytest.approx(6.0))

    response = client.post("/api/presets/open/recall")
    assert response.get_json() == {"ok": True, "skipped": []}
    _wait_for(lambda: _position(client, controller, "CSU-0") == pytest.approx(4.0)
              and _position(client, controller, "CSU-1") == pytest.approx(0.0))


def test_recall_skips_disabled_bars(client: FlaskClient, controller: Controller) -> None:
    _take_control(client)
    client.post("/api/presets", json={"name": "home"})
    client.post("/api/axes/CSU-1/enable", json={})
    response = client.post("/api/presets/home/recall")
    assert response.get_json()["skipped"] == ["CSU-0"]


def test_recall_out_of_travel_moves_nothing(axes: AxisSet, tmp_path: Path) -> None:
    stored = tmp_path / "hand-edited.json"
    stored.write_text('{"bad": {"CSU-0": 1.0, "CSU-1": 99.0}}')
    controller = Controller(axes, PresetStore(stored))
    client = create_app(controller, None, LAYOUT).test_client()
    _take_control(client)
    for bar in ("CSU-0", "CSU-1"):
        client.post(f"/api/axes/{bar}/enable", json={})
    response = client.post("/api/presets/bad/recall")
    assert response.status_code == 400
    assert "CSU-1" in response.get_json()["error"]
    time.sleep(0.05)
    assert _position(client, controller, "CSU-0") == pytest.approx(0.0)


def test_save_points_survive_a_restart(presets_path: Path) -> None:
    PresetStore(presets_path).save("near center", {"CSU-0": SavedBar(1.5, enabled=True)})
    reopened = PresetStore(presets_path)
    assert reopened.names() == ["near center"]
    assert reopened.get("near center")["CSU-0"] == SavedBar(1.5, enabled=True)


def test_save_points_without_enabled_state_still_load(presets_path: Path) -> None:
    presets_path.write_text('{"StatusQuo": {"CSU-0": -437.052}}')
    assert PresetStore(presets_path).get("StatusQuo")["CSU-0"] == SavedBar(-437.052)


def test_save_point_records_enabled_states(client: FlaskClient) -> None:
    _take_control(client)
    client.post("/api/axes/CSU-1/enable", json={})
    client.post("/api/presets", json={"name": "working"})
    saved = client.get("/api/presets/working").get_json()
    assert saved["CSU-0"] == {"position": 0.0, "enabled": False}
    assert saved["CSU-1"] == {"position": 0.0, "enabled": True}


def test_viewing_a_save_point_needs_no_control(client: FlaskClient) -> None:
    _take_control(client)
    client.post("/api/presets", json={"name": "open"})
    client.delete("/api/control")
    assert client.get("/api/presets/open").status_code == 200
    assert client.get("/api/presets/missing").status_code == 404


def test_save_points_need_control(client: FlaskClient) -> None:
    assert client.post("/api/presets", json={"name": "x"}).status_code == 400
    assert client.post("/api/presets/x/recall").status_code == 400


def test_delete_save_point(client: FlaskClient) -> None:
    _take_control(client)
    client.post("/api/presets", json={"name": "tmp"})
    assert client.delete("/api/presets/tmp").status_code == 200
    assert client.get("/api/status").get_json()["presets"] == []
    assert client.delete("/api/presets/tmp").status_code == 400


def test_poll_error_reopens_the_transport(
    controller: Controller, axes: AxisSet, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def lost_link() -> dict[str, Any]:
        raise OSError("Broken pipe")

    monkeypatch.setattr(next(iter(axes)), "status", lost_link)
    monkeypatch.setattr(axes.backend, "close", lambda: calls.append("close"))
    monkeypatch.setattr(axes.backend, "open", lambda: calls.append("open"))
    controller.refresh()
    assert calls == ["close", "open"]
    assert "Broken pipe" in controller.status(None)["error"]


def test_stop_all_needs_no_control(client: FlaskClient) -> None:
    assert client.post("/api/stop").status_code == 200


def test_stop_all_continues_past_a_failed_axis(
    client: FlaskClient, controller: Controller, monkeypatch: pytest.MonkeyPatch
) -> None:
    stopped = []

    def stop(axis: Any) -> None:
        if axis.name == "CSU-0":
            raise OSError("ADS link lost")
        stopped.append(axis.name)

    monkeypatch.setattr("cooethercat.axis.Axis.stop", stop)
    response = client.post("/api/stop")
    assert response.status_code == 502
    assert "CSU-0" in response.get_json()["error"]
    assert stopped == ["CSU-1"]


def test_controller_stop_disables_axes(controller: Controller) -> None:
    token = controller.acquire("alice", None)
    controller.command(token, "CSU-0", "enable")

    def all_disabled() -> bool:
        controller.refresh()
        return not any(axis["enabled"] for axis in controller.status(None)["axes"])

    controller.stop()
    _wait_for(all_disabled)


def test_camera_runs_only_while_watched(camera: SharedCamera) -> None:
    frames = camera.frames()
    assert next(frames) == JPEG
    assert camera.running and camera.viewers == 1
    frames.close()
    assert not camera.running and camera.viewers == 0
    assert FakeSource.instances[0].closed.is_set()


def test_camera_shares_one_capture(camera: SharedCamera) -> None:
    first, second = camera.frames(), camera.frames()
    assert next(first) == JPEG and next(second) == JPEG
    assert len(FakeSource.instances) == 1
    first.close()
    assert camera.running
    second.close()
    assert not camera.running


def test_camera_restarts_for_a_later_viewer(camera: SharedCamera) -> None:
    first = camera.frames()
    assert next(first) == JPEG
    first.close()
    second = camera.frames()
    assert next(second) == JPEG
    second.close()
    assert len(FakeSource.instances) == 2


def test_stream_is_multipart_jpeg(client: FlaskClient) -> None:
    response = client.get("/stream.mjpg", buffered=False)
    assert response.mimetype == "multipart/x-mixed-replace"
    chunk = next(iter(response.response))
    assert chunk.startswith(b"--frame\r\nContent-Type: image/jpeg") and JPEG in chunk
    response.close()


def test_layout_endpoint_lists_placed_bars(client: FlaskClient) -> None:
    layout = client.get("/api/layout").get_json()
    assert layout == {"rows": 12, "bars": {"CSU-0": {"side": "left", "row": 7, "plus": "left"}}}


def test_repo_layout_loads() -> None:
    layout = load_layout(REPO_LAYOUT)
    assert layout.slot("CSU-6") == Slot(Side.LEFT, 5, Side.RIGHT)
    assert layout.slot("CSU-18") == Slot(Side.RIGHT, 5, Side.RIGHT)
    assert layout.slot("CSU-10") == Slot(Side.LEFT, 1, Side.RIGHT)
    assert layout.slot("CSU-11") is None


@pytest.mark.parametrize(
    ("bars", "message"),
    [
        ("{CSU-0: {side: left, row: 1, plus: left}, CSU-1: {side: left, row: 1, plus: left}}",
         "both sit left row 1"),
        ("{CSU-0: {side: left, row: 13, plus: left}}", "outside 1..12"),
        ("{CSU-0: {side: up, row: 1, plus: left}}", "up"),
        ("{CSU-0: {side: left, row: 1, plus: left, colour: red}}", "unknown keys"),
    ],
)
def test_layout_rejects_ambiguous_files(tmp_path: Path, bars: str, message: str) -> None:
    path = tmp_path / "csu.yaml"
    path.write_text(f"placement:\n  rows: 12\n  bars: {bars}\n")
    with pytest.raises(LayoutError, match=message):
        load_layout(path)
