"""CSU keywords exercised through libby's registry against simulated bars."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from cooethercat import AxisSet
from cooethercat.backends.sim import SimBackend, open_simulated
from cooethercat.config import Backend, parse_topology
from libby.keyword import Keyword
from libby.keyword_registry import KeywordRegistry



def load_daemon() -> Any:
    """Import the extensionless daemons/csu/csu script as a module, beside its own modules."""
    folder = Path(__file__).parent.parent / "daemons" / "csu"
    sys.path.insert(0, str(folder))
    path = folder / "csu"
    loader = importlib.machinery.SourceFileLoader("csu_daemon", str(path))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module


csu = load_daemon()
TELEMETRY, CsuKeywords = sys.modules["csu_keywords"].TELEMETRY, csu.CsuKeywords

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


@pytest.fixture(name="axes")
def axes_fixture() -> Iterator[AxisSet]:
    with open_simulated(parse_topology(TOPOLOGY)) as axes:
        yield axes


@pytest.fixture(name="keywords")
def keywords_fixture(axes: AxisSet) -> dict[str, Keyword]:
    registry = KeywordRegistry()
    CsuKeywords(axes).register(registry)
    return {keyword.name: keyword for keyword in registry.drain()}


def read(keywords: dict[str, Keyword], name: str) -> Any:
    reply = keywords[name].handle({})
    assert reply.get("ok", True), reply
    return reply["value"]


def fire(keywords: dict[str, Keyword], name: str) -> None:
    reply = keywords[name].handle({"value": True})
    assert reply.get("ok", True), reply


def wait_for(predicate: Callable[[], bool], timeout_s: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not predicate():
        assert time.monotonic() < deadline, "condition not reached"
        time.sleep(0.01)


def test_every_bar_gets_its_keywords(keywords: dict[str, Keyword]) -> None:
    per_bar = {"positionvalue", "velocity", "ismoving", "isenabled", "error", "halt", "reset",
               *(item.keyword for item in TELEMETRY)}
    expected = {f"{name}{n}" for name in per_bar for n in (0, 6)} | {"ismoving", "halt", "status", "telemetry"}
    assert set(keywords) == expected


def test_enable_and_move_through_keywords(keywords: dict[str, Keyword]) -> None:
    assert read(keywords, "isenabled6") is False
    keywords["isenabled6"].handle({"value": True})
    assert read(keywords, "isenabled6") is True
    keywords["velocity6"].handle({"value": 40.0})
    keywords["positionvalue6"].handle({"value": 7.5})
    wait_for(lambda: read(keywords, "positionvalue6") == pytest.approx(7.5))
    assert read(keywords, "ismoving") is False


def test_move_without_velocity_uses_the_limit(axes: AxisSet, keywords: dict[str, Keyword]) -> None:
    keywords["isenabled0"].handle({"value": True})
    axes.axis("CSU-0").set("velocity", 0.0)
    keywords["positionvalue0"].handle({"value": 3.0})
    wait_for(lambda: read(keywords, "positionvalue0") == pytest.approx(3.0))


def test_move_outside_travel_is_an_error_reply(keywords: dict[str, Keyword]) -> None:
    keywords["isenabled0"].handle({"value": True})
    reply = keywords["positionvalue0"].handle({"value": 99.0})
    assert reply.get("ok") is False
    assert read(keywords, "positionvalue0") == pytest.approx(0.0)


def test_velocity_above_limit_is_refused(keywords: dict[str, Keyword]) -> None:
    assert keywords["velocity0"].handle({"value": 500.0}).get("ok") is False


def test_halt_stops_a_moving_bar(keywords: dict[str, Keyword]) -> None:
    keywords["isenabled6"].handle({"value": True})
    keywords["velocity6"].handle({"value": 1.0})
    keywords["positionvalue6"].handle({"value": 15.0})
    wait_for(lambda: read(keywords, "ismoving6"))
    fire(keywords, "halt")
    wait_for(lambda: not read(keywords, "ismoving6"))
    assert read(keywords, "positionvalue6") < 15.0


def test_fault_is_reported_and_reset(axes: AxisSet, keywords: dict[str, Keyword]) -> None:
    backend = axes.backend
    assert isinstance(backend, SimBackend)
    backend.inject_fault("CSU-0", error_id=0x4650)
    assert read(keywords, "error0") == 0x4650
    fire(keywords, "reset0")
    assert read(keywords, "error0") == 0


def test_telemetry_is_scaled(axes: AxisSet, keywords: dict[str, Keyword]) -> None:
    backend = axes.backend
    assert isinstance(backend, SimBackend)
    backend.set_object("CSU-6", 0x3201, 1, 724)
    backend.set_object("CSU-6", 0x2200, 1, 233)
    assert read(keywords, "boardtemp6") == pytest.approx(72.4)
    assert read(keywords, "supply6") == pytest.approx(23.3)


def test_status_covers_every_bar(keywords: dict[str, Keyword]) -> None:
    keywords["isenabled6"].handle({"value": True})
    status = json.loads(read(keywords, "status"))
    assert set(status) == {"CSU-0", "CSU-6"}
    assert status["CSU-6"]["enabled"] is True
    assert status["CSU-0"]["position"] == pytest.approx(0.0)


def test_telemetry_reads_every_bar(axes: AxisSet, keywords: dict[str, Keyword]) -> None:
    backend = axes.backend
    assert isinstance(backend, SimBackend)
    backend.set_object("CSU-6", 0x3201, 1, 712)
    backend.set_object("CSU-6", 0x30D1, 1, 150)
    readings = json.loads(read(keywords, "telemetry"))
    assert readings["CSU-6"] == {"boardtemp": pytest.approx(71.2), "current": pytest.approx(150.0)}
    assert set(readings) == {"CSU-0", "CSU-6"}


def test_link_down_fails_every_bar_keyword_at_once(axes: AxisSet) -> None:
    registry = KeywordRegistry()
    CsuKeywords(axes, online=lambda: False).register(registry)
    keywords = {keyword.name: keyword for keyword in registry.drain()}
    for name in ("positionvalue0", "boardtemp6", "status", "telemetry"):
        reply = keywords[name].handle({})
        assert reply["ok"] is False and "PLC unreachable" in reply["error"]


CSU_CONFIG = Path(__file__).parent.parent / "config" / "csu" / "csu.yaml"


def load_csu_config() -> dict[str, Any]:
    """Return the deployed CSU daemon config."""
    with CSU_CONFIG.open(encoding="utf-8") as handle:
        config: dict[str, Any] = yaml.safe_load(handle)
    return config


@pytest.mark.parametrize("master", ["twincat", "pysoem"])
def test_csu_config_parses_under_either_master(master: str) -> None:
    config = load_csu_config()
    topology = csu.csu_topology(config["topology"], config["transports"], master, sim=False)
    assert topology.backend.value == master
    assert len(topology.axes) == 23
    assert all(axis.slave_index == int(axis.name.split("-")[1]) for axis in topology.axes)
    assert topology.axes[0].units.to_increments(1.0) == 10000


def test_sim_ignores_the_master() -> None:
    config = load_csu_config()
    topology = csu.csu_topology(config["topology"], config["transports"], "pysoem", sim=True)
    assert topology.backend is Backend.SIM


def test_every_master_has_an_opener() -> None:
    assert set(csu.OPENERS) == set(Backend)
