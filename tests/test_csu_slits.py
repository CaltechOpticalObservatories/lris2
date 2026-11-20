"""CSU slit keywords over simulated bars, with lris2-csu's bar pair geometry."""

from __future__ import annotations

import importlib
import json
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from cooethercat import AxisSet
from cooethercat.backends.sim import open_simulated
from cooethercat.config import parse_topology
from libby.keyword import Keyword
from libby.keyword_registry import KeywordRegistry

sys.path.insert(0, str(Path(__file__).parent.parent / "daemons" / "csu"))
csu_keywords = importlib.import_module("csu_keywords")
csu_slits = importlib.import_module("csu_slits")

CONFIG = Path(__file__).parent.parent / "config" / "csu" / "csu.yaml"
# Row 1 is a full pair; row 2 has only its left bar
PLACEMENT: dict[str, Any] = {"bars": {
    "CSU-0": {"side": "left", "row": 1, "plus": "right"},
    "CSU-1": {"side": "right", "row": 1, "plus": "left"},
    "CSU-2": {"side": "left", "row": 2, "plus": "left"},
}}
TOPOLOGY: dict[str, Any] = {
    "name": "csu-sim",
    "backend": "sim",
    "transport": {"tick_s": 0.002},
    "defaults": {
        "units": {"name": "mm"},
        "limits": {"velocity": 2000.0, "min_position": -300.0, "max_position": 300.0},
    },
    "axes": [{"name": "CSU-0"}, {"name": "CSU-1"}, {"name": "CSU-2"}],
}


@pytest.fixture(name="keywords")
def keywords_fixture() -> Iterator[dict[str, Keyword]]:
    """Serve the bar and slit keywords of three simulated, enabled, fast bars."""
    with open_simulated(parse_topology(TOPOLOGY)) as axes:
        registry = KeywordRegistry()
        bars = csu_keywords.CsuKeywords(axes)
        bars.register(registry)
        geometry = csu_slits.slit_geometry(PLACEMENT, {axis.name for axis in axes})
        csu_slits.SlitKeywords(axes, geometry, bars).register(registry)
        keywords = {keyword.name: keyword for keyword in registry.drain()}
        enable(axes, keywords)
        yield keywords


def enable(axes: AxisSet, keywords: dict[str, Keyword]) -> None:
    """Energise every bar and give it a fast profile velocity."""
    for n in range(len(axes)):
        assert keywords[f"isenabled{n}"].handle({"value": True}).get("ok", True)
        assert keywords[f"velocity{n}"].handle({"value": 2000.0}).get("ok", True)


def read(keywords: dict[str, Keyword], name: str) -> Any:
    """Return a keyword's value, failing on an error reply."""
    reply = keywords[name].handle({})
    assert reply.get("ok", True), reply
    return reply["value"]


def wait_for(predicate: Callable[[], bool], timeout_s: float = 3.0) -> None:
    """Poll until predicate holds."""
    deadline = time.monotonic() + timeout_s
    while not predicate():
        assert time.monotonic() < deadline, "condition not reached"
        time.sleep(0.01)


def set_mask(keywords: dict[str, Keyword], mask: dict[str, list[float]]) -> dict[str, Any]:
    """Write maskconfig and return the reply."""
    reply: dict[str, Any] = keywords["maskconfig"].handle({"value": json.dumps(mask)})
    return reply


def test_shipped_placement_forms_full_and_one_bar_pairs() -> None:
    """The CSU config's placement gives five full pairs and six left-only rows."""
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    names = {axis["name"] for axis in config["topology"]["axes"]}
    geometry = csu_slits.slit_geometry(config["placement"], names)
    full = {row for row, pair in geometry.bar_pairs.items() if pair.left and pair.right}
    left_only = {row for row, pair in geometry.bar_pairs.items() if pair.right is None}
    assert full == {5, 9, 10, 11, 12}
    assert left_only == {1, 2, 3, 4, 7, 8}
    assert geometry.bar_pairs[5].left.bus_id == 6 and geometry.bar_pairs[5].right.bus_id == 18


@pytest.mark.parametrize(("bar_name", "reversed_"), [("CSU-0", True), ("CSU-6", False),
                                                 ("CSU-13", False), ("CSU-18", True)])
def test_a_bar_moving_towards_its_own_side_is_reversed(bar_name: str, reversed_: bool) -> None:
    """A positive move that retracts a bar makes it reversed."""
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    names = {axis["name"] for axis in config["topology"]["axes"]}
    geometry = csu_slits.slit_geometry(config["placement"], names)
    assert geometry.bar_configs[int(bar_name.split("-")[1])].reversed is reversed_


@pytest.mark.parametrize(("bars", "message"), [
    ({"CSU-9": {"side": "left", "row": 1, "plus": "left"}}, "not a configured bar"),
    ({"CSU-0": {"side": "left", "row": 1, "plus": "left"},
      "CSU-1": {"side": "left", "row": 1, "plus": "left"}}, "both sit left row 1"),
    ({"CSU-0": {"side": "up", "row": 1, "plus": "left"}}, "left or right"),
])
def test_bad_placement_is_refused(bars: dict[str, Any], message: str) -> None:
    """Placement naming an unknown bar, a taken slot or a bad side is refused at start."""
    with pytest.raises(ValueError, match=message):
        csu_slits.slit_geometry({"bars": bars}, {"CSU-0", "CSU-1"})


def test_every_pair_gets_slit_keywords(keywords: dict[str, Keyword]) -> None:
    """Each placed row has a center and a width keyword, plus one mask keyword."""
    slit_keywords = {name for name in keywords if name.startswith(("slit", "mask"))}
    assert slit_keywords == {"maskconfig", "slitcenter1", "slitwidth1", "slitcenter2", "slitwidth2"}


def test_mask_moves_both_bars_of_a_full_pair(keywords: dict[str, Keyword]) -> None:
    """A slit on a full pair puts the left bar at its left edge and the right bar at its right."""
    assert set_mask(keywords, {"1": [20.0, 20.0]}).get("ok", True)
    wait_for(lambda: not read(keywords, "ismoving"))
    assert read(keywords, "positionvalue0") == pytest.approx(10.0)
    assert read(keywords, "positionvalue1") == pytest.approx(230.0)
    assert read(keywords, "slitcenter1") == pytest.approx(20.0)
    assert read(keywords, "slitwidth1") == pytest.approx(20.0)


def test_mask_reads_back_for_full_and_one_bar_pairs(keywords: dict[str, Keyword]) -> None:
    """maskconfig returns the slits it was set to."""
    mask = {"1": [100.0, 30.0], "2": [135.0, 250.0]}
    assert set_mask(keywords, mask).get("ok", True)
    wait_for(lambda: not read(keywords, "ismoving"))
    back = json.loads(read(keywords, "maskconfig"))
    assert back == {pair: pytest.approx(slit) for pair, slit in mask.items()}
    assert read(keywords, "positionvalue2") == pytest.approx(-10.0)


@pytest.mark.parametrize("mask", [{"2": [50.0, 20.0]}, {"7": [100.0, 10.0]},
                                  {"1": [300.0, 10.0]}, {"1": "wide"}])
def test_invalid_mask_moves_nothing(keywords: dict[str, Keyword], mask: dict[str, Any]) -> None:
    """A slit needing a missing bar, an unknown pair, or one outside the opening is refused."""
    reply = keywords["maskconfig"].handle({"value": json.dumps(mask)})
    assert reply.get("ok") is False
    assert not read(keywords, "ismoving")
    assert [read(keywords, f"positionvalue{n}") for n in range(3)] == [0.0, 0.0, 0.0]


def test_mask_is_refused_while_its_bars_move(keywords: dict[str, Keyword]) -> None:
    """A second mask while the first still moves is refused."""
    assert keywords["velocity1"].handle({"value": 1.0}).get("ok", True)
    assert set_mask(keywords, {"1": [20.0, 20.0]}).get("ok", True)
    reply = set_mask(keywords, {"1": [40.0, 20.0]})
    assert reply.get("ok") is False
    assert "already moving" in str(reply)
