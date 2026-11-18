"""Drive telemetry history kept in memory for the per-bar charts, and a periodic poller."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any, Final

HISTORY_S: Final = 2 * 3600.0
POLL_S: Final = 10.0

_log = logging.getLogger(__name__)


class TelemetryHistory:
    """Timestamped readings per bar, trimmed to a fixed window."""

    def __init__(self, window_s: float = HISTORY_S) -> None:
        self._window_s = window_s
        self._lock = threading.Lock()
        self._samples: dict[str, deque[tuple[float, dict[str, float | None]]]] = {}

    def add(self, when: float, readings: dict[str, dict[str, float | None]]) -> None:
        """Record one reading of every bar taken at ``when`` (epoch seconds)."""
        with self._lock:
            for bar_name, values in readings.items():
                samples = self._samples.setdefault(bar_name, deque())
                samples.append((when, values))
                while samples and samples[0][0] < when - self._window_s:
                    samples.popleft()

    def series(self, bar_name: str) -> dict[str, list[Any]]:
        """Return one bar's history as parallel lists: time, then one list per reading."""
        with self._lock:
            samples = list(self._samples.get(bar_name, ()))
        keys = sorted({key for _, values in samples for key in values})
        return {"time": [when for when, _ in samples],
                **{key: [values.get(key) for _, values in samples] for key in keys}}


class Poller:
    """Call a function every period on a daemon thread, logging the errors it is told to expect."""

    def __init__(self, name: str, period_s: float, call: Callable[[], None],
                 errors: tuple[type[Exception], ...]) -> None:
        self._call = call
        self._errors = errors
        self._period_s = period_s
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)

    def start(self) -> None:
        """Begin polling."""
        self._thread.start()

    def stop(self) -> None:
        """Stop polling and wait for the thread."""
        self._stop.set()
        self._thread.join(timeout=2.0)

    def _run(self) -> None:
        while True:
            try:
                self._call()
            except self._errors as error:
                _log.warning("%s: %s", self._thread.name, error)
            if self._stop.wait(self._period_s):
                return


def record_telemetry(read: Callable[[], str], history: TelemetryHistory,
                     clock: Callable[[], float] = time.time) -> Callable[[], None]:
    """Return a poll step that reads the daemon's telemetry JSON into ``history``."""
    def step() -> None:
        history.add(clock(), json.loads(read()))
    return step
