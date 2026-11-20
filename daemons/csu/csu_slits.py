"""CSU slit keywords: slits on bar pairs, converted to bar positions by lris2-csu."""
import json
from collections.abc import Collection, Mapping
from typing import Any, Final

from cooethercat import AxisError, AxisSet
from lris2csu.geometry import BarConfig, BarPairConfig, CSUHardwareConfig
from lris2csu.slit import MaskConfig

from csu_keywords import CsuKeywords, Registry, bar_number

SIDES: Final = ("left", "right")


def slit_geometry(placement: Mapping[str, Any], bar_names: Collection[str]) -> CSUHardwareConfig:
    """Return one bar pair per row with a bar placed, keyed by row.

    A bar whose positive move takes it towards its own side is reversed, so
    either way a larger travel closes the slit.
    """
    rows: dict[int, dict[str, BarConfig]] = {}
    for name, slot in (placement.get("bars") or {}).items():
        if name not in bar_names:
            raise ValueError(f"placement: {name} is not a configured bar")
        side, row, plus = slot["side"], int(slot["row"]), slot["plus"]
        if side not in SIDES or plus not in SIDES:
            raise ValueError(f"placement: {name} side and plus must be left or right")
        if side in rows.setdefault(row, {}):
            raise ValueError(f"placement: {name} and bar {rows[row][side].bus_id} both sit "
                             f"{side} row {row}")
        reversed_ = plus == side
        rows[row][side] = BarConfig(int(name.rsplit("-", 1)[1]), reversed=reversed_,
                                    um_per_count=-1.0 if reversed_ else 1.0)
    pairs = [BarPairConfig(row, **bars) for row, bars in sorted(rows.items())]
    return CSUHardwareConfig(ethercat_device="", bar_pairs=pairs, left_brake=None, right_brake=None)


class SlitKeywords:
    """Serve the CSU as slits: one per bar pair, set together as a mask."""

    def __init__(self, axes: AxisSet, geometry: CSUHardwareConfig, bars: CsuKeywords) -> None:
        self._geometry = geometry
        self._bars = bars
        placed = geometry.bar_configs
        self._axes = {bar_number(axis): axis for axis in axes if bar_number(axis) in placed}

    def register(self, registry: Registry) -> None:
        """Register the mask keyword and each pair's slit center and width."""
        guard = self._bars.guard
        registry.string("maskconfig", getter=guard(self.mask_json),
                        setter=guard(lambda text: self.set_mask(str(text))),
                        description="Slits as JSON {pair: [center mm, width mm]}; "
                                    "a write moves the placed bars of each pair named")
        for pair in self._geometry.bar_pairs:
            registry.float(f"slitcenter{pair}", units="mm",
                           getter=guard(lambda pair=pair: round(self.slits()[pair][0], 4)),
                           description=f"Center of the slit in row {pair}")
            registry.float(f"slitwidth{pair}", units="mm",
                           getter=guard(lambda pair=pair: round(self.slits()[pair][1], 4)),
                           description=f"Width of the slit in row {pair}")

    def slits(self) -> dict[int, tuple[float, float]]:
        """Return every pair's (center, width) in mm from the bars' positions."""
        positions = {number: axis.position for number, axis in self._axes.items()}
        return self._geometry.compute_pos_width_dict_mm(positions)

    def mask_json(self) -> str:
        """Return the current slits as {pair: [center, width]}."""
        return json.dumps({pair: [round(center, 4), round(width, 4)]
                           for pair, (center, width) in self.slits().items()})

    def set_mask(self, text: str) -> None:
        """Validate a mask, then start moving the placed bars of every pair it names."""
        try:
            mask = MaskConfig.from_dict(json.loads(text))  # type: ignore[no-untyped-call]
            targets = self._geometry.compute_bar_mm_positions(mask.to_dict())
        except (KeyError, TypeError, ValueError) as error:
            raise AxisError(f"invalid mask: {error}") from error
        axes = [(self._axes[number], target) for number, target in targets.items()]
        moving = [axis.name for axis, _ in axes if axis.moving]
        if moving:
            raise AxisError(f"{', '.join(moving)} already moving")
        for axis, target in axes:
            self._bars.move_to(axis, target)
