"""Where each CSU bar sits physically, as seen from the webcam."""

from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class LayoutError(ValueError):
    """Raised for a layout file that would mislabel a bar."""


class Side(enum.StrEnum):
    """Side of the slit a bar enters from, on screen."""

    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True)
class Slot:
    """One bar's physical slot and the on-screen direction of a positive move."""

    side: Side
    row: int
    plus: Side


@dataclass(frozen=True)
class Layout:
    """Rows of the CSU and the slot of every bar in service."""

    rows: int
    slots: Mapping[str, Slot]

    def slot(self, bar: str) -> Slot | None:
        """Return a bar's slot, or None when the bar is not placed."""
        return self.slots.get(bar)


def load_layout(path: Path) -> Layout:
    """Read and validate a layout file."""
    data = yaml.safe_load(path.read_text()) or {}
    _reject_unknown(data, {"rows", "bars"}, str(path))
    rows = int(data.get("rows", 12))
    slots = {str(bar): _slot(entry, rows, f"{path}: {bar}") for bar, entry in (data.get("bars") or {}).items()}
    taken: dict[tuple[Side, int], str] = {}
    for bar, slot in slots.items():
        other = taken.setdefault((slot.side, slot.row), bar)
        if other != bar:
            raise LayoutError(f"{path}: {bar} and {other} both sit {slot.side} row {slot.row}")
    return Layout(rows, slots)


def _slot(entry: Any, rows: int, where: str) -> Slot:
    if not isinstance(entry, Mapping):
        raise LayoutError(f"{where}: expected side, row and plus")
    _reject_unknown(entry, {"side", "row", "plus"}, where)
    try:
        slot = Slot(Side(entry["side"]), int(entry["row"]), Side(entry["plus"]))
    except (KeyError, ValueError) as error:
        raise LayoutError(f"{where}: {error}") from None
    if not 1 <= slot.row <= rows:
        raise LayoutError(f"{where}: row {slot.row} is outside 1..{rows}")
    return slot


def _reject_unknown(data: Mapping[str, Any], allowed: set[str], where: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise LayoutError(f"{where}: unknown keys {sorted(unknown)}")
