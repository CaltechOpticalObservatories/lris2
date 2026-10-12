"""``lris2``: deploy, run and inspect the LRIS2 daemons on this host.

Every command comes from instrumentctl, which is shared with the other
instruments. All that is specific to LRIS2 is ``instrument.toml`` beside this
file.
"""

from importlib import resources
from pathlib import Path
from typing import List, Optional

from instrumentctl import run


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for the ``lris2`` console script."""
    config = resources.files(__package__).joinpath("instrument.toml")
    # Locates the checkout under an editable install, which is what lets the
    # deployed CLI follow a git pull
    return run(config, repo_hint=Path(__file__).resolve().parents[2], argv=argv)
