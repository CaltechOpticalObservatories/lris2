"""Named save points, each holding every bar's position and enabled state, in a JSON file."""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

MAX_NAME_LENGTH: Final = 40


class PresetError(ValueError):
    """Raised for an unknown or invalid save point."""


@dataclass(frozen=True)
class SavedBar:
    """One bar as it was when the save point was taken."""

    position: float
    enabled: bool | None = None


class PresetStore:
    """Save points shared by every viewer and persisted across restarts."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._presets: dict[str, dict[str, SavedBar]] = self._load()

    def names(self) -> list[str]:
        """Return save point names in the order they were created."""
        with self._lock:
            return list(self._presets)

    def get(self, name: str) -> Mapping[str, SavedBar]:
        """Return one save point by bar name."""
        with self._lock:
            try:
                return MappingProxyType(dict(self._presets[name]))
            except KeyError:
                raise PresetError(f"no save point {name!r}") from None

    def save(self, name: str, bars: Mapping[str, SavedBar]) -> None:
        """Store or overwrite a save point."""
        name = name.strip()
        if not name or len(name) > MAX_NAME_LENGTH:
            raise PresetError(f"save point names are 1 to {MAX_NAME_LENGTH} characters")
        with self._lock:
            self._presets[name] = dict(bars)
            self._write()

    def delete(self, name: str) -> None:
        """Remove a save point."""
        with self._lock:
            if self._presets.pop(name, None) is None:
                raise PresetError(f"no save point {name!r}")
            self._write()

    def _load(self) -> dict[str, dict[str, SavedBar]]:
        if not self._path.exists():
            return {}
        raw = json.loads(self._path.read_text())
        return {str(name): {str(bar_name): _saved_bar(entry) for bar_name, entry in bars.items()}
                for name, bars in raw.items()}

    def _write(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        staging = self._path.with_suffix(".tmp")
        payload = {name: {bar_name: asdict(saved) for bar_name, saved in bars.items()}
                   for name, bars in self._presets.items()}
        staging.write_text(json.dumps(payload, indent=2))
        os.replace(staging, self._path)


def _saved_bar(entry: Any) -> SavedBar:
    # Save points written before enabled states were recorded hold a bare position
    if isinstance(entry, int | float):
        return SavedBar(float(entry))
    enabled = entry.get("enabled")
    return SavedBar(float(entry["position"]), None if enabled is None else bool(enabled))
