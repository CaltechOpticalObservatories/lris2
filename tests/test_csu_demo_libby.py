"""The demo's libby backend, driven against the CSU daemon's keywords on simulated bars."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from cooethercat import Axis, AxisError, AxisSet, ControllerState
from cooethercat.backends.sim import open_simulated
from cooethercat.config import parse_topology
from libby.keyword import Keyword
from libby.keyword_registry import KeywordRegistry
from lris2.csu.keywords import CsuKeywords
from lris2.csu_demo.control import ControlError, Controller
from lris2.csu_demo.history import TelemetryHistory, record_telemetry
from lris2.csu_demo.layout import Layout
from lris2.csu_demo.libby_backend import LibbyBackend
from lris2.csu_demo.power import OUTLETS, PowerPanel
from lris2.csu_demo.presets import PresetStore
from lris2.csu_demo.web import create_app

TOPOLOGY: dict[str, Any] = {
    "name": "csu-sim",
    "backend": "sim",
    "transport": {"tick_s": 0.002},
    "defaults": {
        "units": {"name": "mm"},
        "limits": {"velocity": 50.0, "min_position": -20.0, "max_position": 20.0},
    },
    "axes": [{"name": "CSU-0"}, {"name": "CSU-6"}],
}


class DaemonClient:
    """Answer libby gets and sets from the CSU keywords, as the daemon would."""

    def __init__(self, keywords: dict[str, Keyword]) -> None:
        self.keywords = keywords
        self.status_reads = 0

    def get(self, name: str, *, timeout_s: float = 2.0) -> Any:
        keyword = name.removeprefix("lris2.csu.")
        self.status_reads += keyword == "status"
        if keyword == "plcstate":
            return "run"
        return self._reply(self.keywords[keyword].handle({}))

    def set(self, name: str, value: Any, *, timeout_s: float | None = None) -> Any:
        return self._reply(self.keywords[name.removeprefix("lris2.csu.")].handle({"value": value}))

    @staticmethod
    def _reply(reply: dict[str, Any]) -> Any:
        if reply.get("ok", True) is False:
            raise RuntimeError(reply.get("error", "keyword failed"))
        return reply.get("value")


@pytest.fixture(name="daemon_axes")
def daemon_axes_fixture() -> Iterator[AxisSet]:
    with open_simulated(parse_topology(TOPOLOGY)) as axes:
        yield axes


@pytest.fixture(name="client")
def client_fixture(daemon_axes: AxisSet) -> DaemonClient:
    registry = KeywordRegistry()
    CsuKeywords(daemon_axes).register(registry)
    return DaemonClient({keyword.name: keyword for keyword in registry.drain()})


@pytest.fixture(name="axes")
def axes_fixture(client: DaemonClient) -> AxisSet:
    backend = LibbyBackend(client)
    topology = parse_topology(TOPOLOGY)
    axes = AxisSet(backend, {config.keyword_name: Axis(backend, config) for config in topology.axes})
    backend.open()
    return axes


def wait_for(predicate: Callable[[], bool], timeout_s: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not predicate():
        assert time.monotonic() < deadline, "condition not reached"
        time.sleep(0.01)


def test_enable_and_relative_move(axes: AxisSet, daemon_axes: AxisSet) -> None:
    bar = axes.axis("CSU-6")
    bar.enable()
    bar.move_relative(4.0, velocity=40.0, wait=False)
    wait_for(lambda: daemon_axes.axis("CSU-6").position == pytest.approx(4.0))
    bar.move_relative(-1.5, velocity=40.0, wait=False)
    wait_for(lambda: daemon_axes.axis("CSU-6").position == pytest.approx(2.5))


def test_absolute_move_and_halt(axes: AxisSet, daemon_axes: AxisSet) -> None:
    bar = axes.axis("CSU-0")
    bar.enable()
    bar.move_absolute(15.0, velocity=1.0, wait=False)
    wait_for(lambda: daemon_axes.axis("CSU-0").moving)
    bar.stop()
    wait_for(lambda: not daemon_axes.axis("CSU-0").moving)
    assert daemon_axes.axis("CSU-0").position < 15.0


def test_one_status_read_serves_every_bar(axes: AxisSet, client: DaemonClient) -> None:
    for bar in axes:
        bar.status()
    assert client.status_reads == 1


def test_disabled_bar_refuses_to_move(axes: AxisSet) -> None:
    with pytest.raises(AxisError):
        axes.axis("CSU-0").move_relative(1.0, wait=False)


def test_controller_state_comes_from_the_daemon(axes: AxisSet) -> None:
    assert axes.backend.controller_state() is ControllerState.RUN


def test_taking_control_needs_the_password(axes: AxisSet, tmp_path: Any) -> None:
    controller = Controller(axes, PresetStore(tmp_path / "presets.json"), password="s3cret")
    with pytest.raises(ControlError, match="wrong password"):
        controller.acquire("mallory", None, "guess")
    token = controller.acquire("alice", None, "s3cret")
    assert controller.acquire("alice", token) == token


class FakePdu:
    """The CSU lab PDU's outlet keywords."""

    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        for name, _ in OUTLETS:
            self.values |= {f"state_{name}": True, f"power_{name}": 10.0, f"current_{name}": 0.1}

    def get(self, name: str, *, timeout_s: float = 2.0) -> Any:
        return self.values[name.removeprefix("l2power.pdu-ethercat.")]

    def set(self, name: str, value: Any, *, timeout_s: float | None = None) -> Any:
        self.values[name.removeprefix("l2power.pdu-ethercat.")] = value
        return value


def test_history_trims_to_its_window() -> None:
    history = TelemetryHistory(window_s=100.0)
    history.add(0.0, {"CSU-6": {"boardtemp": 60.0, "current": 0.0}})
    history.add(50.0, {"CSU-6": {"boardtemp": 61.0, "current": None}})
    history.add(150.0, {"CSU-6": {"boardtemp": 62.0, "current": 5.0}})
    assert history.series("CSU-6") == {"time": [50.0, 150.0], "boardtemp": [61.0, 62.0],
                                       "current": [None, 5.0]}
    assert history.series("CSU-0") == {"time": []}


def test_telemetry_poll_records_the_daemon_reading(client: DaemonClient) -> None:
    history = TelemetryHistory()
    record_telemetry(lambda: client.get("lris2.csu.telemetry"), history, clock=lambda: 1.0)()
    assert history.series("CSU-6")["time"] == [1.0]


@pytest.fixture(name="web")
def web_fixture(axes: AxisSet, tmp_path: Any) -> tuple[Any, FakePdu, Controller]:
    pdu = FakePdu()
    controller = Controller(axes, PresetStore(tmp_path / "presets.json"))
    controller.refresh()
    panel = PowerPanel(pdu)
    panel.refresh()
    app = create_app(controller, None, Layout(rows=12, slots={}), history=TelemetryHistory(),
                     power=panel)
    return app.test_client(), pdu, controller


def test_power_status_lists_every_outlet(web: tuple[Any, FakePdu, Controller]) -> None:
    flask_client, _, _ = web
    outlets = flask_client.get("/api/power").get_json()["outlets"]
    assert [outlet["name"] for outlet in outlets] == [name for name, _ in OUTLETS]
    assert [outlet["name"] for outlet in outlets if outlet["switchable"]] == ["ethercat"]


def test_drives_switch_needs_control_and_no_bar_enabled(
    web: tuple[Any, FakePdu, Controller], axes: AxisSet
) -> None:
    flask_client, pdu, controller = web
    assert flask_client.post("/api/power/ethercat", json={"on": False}).status_code == 400
    assert flask_client.post("/api/control", json={}).status_code == 200
    axes.axis("CSU-0").enable()
    controller.refresh()
    refused = flask_client.post("/api/power/ethercat", json={"on": False})
    assert "disable every bar" in refused.get_json()["error"]
    axes.axis("CSU-0").disable()
    controller.refresh()
    assert flask_client.post("/api/power/ethercat", json={"on": False}).status_code == 200
    assert pdu.values["state_ethercat"] is False


def test_only_the_drives_outlet_switches(web: tuple[Any, FakePdu, Controller]) -> None:
    flask_client, pdu, _ = web
    flask_client.post("/api/control", json={})
    assert flask_client.post("/api/power/plc", json={"on": False}).status_code == 400
    assert pdu.values["state_plc"] is True


def test_history_route_serves_every_bar(web: tuple[Any, FakePdu, Controller]) -> None:
    flask_client, _, _ = web
    assert flask_client.get("/api/history").get_json() == {}


def test_all_series_keys_by_bar() -> None:
    history = TelemetryHistory()
    history.add(1.0, {"CSU-0": {"current": 3.0}, "CSU-6": {"current": 4.0}})
    assert history.all_series()["CSU-6"] == {"time": [1.0], "current": [4.0]}
