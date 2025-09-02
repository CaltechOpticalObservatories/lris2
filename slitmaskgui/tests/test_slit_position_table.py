import pytest
from unittest.mock import patch, Mock
from slitmaskgui.slit_position_table import SlitDisplay



@pytest.fixture
def setup_slit_display_class(qtbot):
    slit_display = SlitDisplay()
    slit_display.changed_data_dict = {14:2, 15:3}
    qtbot.addWidget(slit_display)
    return slit_display


def test_data_saved_signal(setup_slit_display_class, qtbot):
    """ This is in test mask config because it has more to do with the mask config than the slit display (data transfer) """
    test_slit_display = setup_slit_display_class

    with qtbot.waitSignal(test_slit_display.data_changed) as bonker:
        test_slit_display.data_saved()
    # assert bonker.args != [test_slit_display.changed_data_dict]
    
    assert test_slit_display.changed_data_dict == {}  # cleared
