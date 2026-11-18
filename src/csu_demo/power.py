"""CSU lab PDU outlets as the demo shows and switches them, through the l2power daemon."""

from __future__ import annotations

import threading
from typing import Any, Final

from .libby_backend import KeywordClient

# Outlet keyword name, label; only the drives may be switched from the page
OUTLETS: Final = (
    ("ethercat", "EtherCAT drives"),
    ("plc", "PLC"),
    ("gateway", "lris2-ethercat"),
    ("windows", "Windows XAE PC"),
    ("lantronix", "Lantronix"),
)
SWITCHABLE: Final = frozenset({"ethercat"})


class PowerError(RuntimeError):
    """Raised when a power switch is refused."""


class PowerPanel:
    """Cache outlet readings and switch the drives outlet."""

    def __init__(self, client: KeywordClient, peer: str = "l2power.csupdu") -> None:
        self._client = client
        self._peer = peer
        self._lock = threading.Lock()
        self._outlets: list[dict[str, Any]] = []
        self._error: str | None = None

    def refresh(self) -> None:
        """Read every outlet's state, power and current."""
        outlets = []
        for name, label in OUTLETS:
            outlets.append({
                "name": name, "label": label, "switchable": name in SWITCHABLE,
                "on": bool(self._get(f"state_{name}")),
                "power": float(self._get(f"power_{name}")),
                "current": float(self._get(f"current_{name}")),
            })
        with self._lock:
            self._outlets, self._error = outlets, None

    def fail(self, error: Exception) -> None:
        """Remember why the last refresh failed, for the page."""
        with self._lock:
            self._error = str(error)

    def status(self) -> dict[str, Any]:
        """Return the cached outlets and the last refresh error."""
        with self._lock:
            return {"outlets": list(self._outlets), "error": self._error}

    def switch(self, outlet: str, on: bool) -> None:
        """Switch one outlet the page may switch."""
        if outlet not in SWITCHABLE:
            raise PowerError(f"{outlet} cannot be switched from here")
        self._client.set(f"{self._peer}.state_{outlet}", on)
        self.refresh()

    def _get(self, keyword: str) -> Any:
        return self._client.get(f"{self._peer}.{keyword}")
