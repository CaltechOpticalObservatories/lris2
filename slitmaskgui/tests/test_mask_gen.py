# from slitmaskgui.backend.mask_gen import SlitMask


import pytest
from slitmaskgui.backend.mask_gen import SlitMask, CSU_HEIGHT, CSU_WIDTH, TOTAL_BAR_PAIRS
"""
will be in a list of obj {name,ra,dec,equinox,vmag,priority,bar_id,x_mm,y_mm}
"""


# print(stars)


def test_check_if_within_bounds():
    sm = SlitMask([])

    assert sm.check_if_within(0, 0) is True
    assert sm.check_if_within(CSU_WIDTH/2 - 0.01, CSU_HEIGHT/2 - 0.01) is True
    assert sm.check_if_within(CSU_WIDTH/2 + 1, 0) is False
    assert sm.check_if_within(0, CSU_HEIGHT/2 + 1) is False

def test_bar_id_assignment_center():
    stars = [{"x_mm": 0, "y_mm": 0, "priority": 1}]
    mask = SlitMask(stars)
    assert "bar_id" in mask.stars[0]
    assert mask.stars[0]["bar_id"] == TOTAL_BAR_PAIRS // 2

def test_out_of_bounds_star_is_removed():
    stars = [
        {"x_mm": 0, "y_mm": 0, "priority": 1},
        {"x_mm": CSU_WIDTH + 1, "y_mm": 0, "priority": 2},  # Should be removed
    ]
    mask = SlitMask(stars)
    assert len(mask.stars) == 1
    assert mask.stars[0]["x_mm"] == 0 and mask.stars[0]["y_mm"] == 0

def test_priority_optimization_per_bar_id():
    stars = [
        {"x_mm":0,"y_mm":1, "priority": 1},
        {"x_mm":0,"y_mm":1, "priority": 3},  # same bar_id, higher priority
        {"x_mm":0,"y_mm":-1, "priority": 2}, #  different bar_id, does not pass if y_mm is positive 40
    ]
    mask = SlitMask(stars)
    result = mask.return_mask()

    # Check: 1 star per bar_id
    bar_ids = [s["bar_id"] for s in result]
    print(bar_ids)
    assert len(bar_ids) == len(result)

    # Check: highest priority per group is kept
    for star in result:
        if star["bar_id"] == mask.stars[0]["bar_id"]:
            assert star["priority"] == 3
