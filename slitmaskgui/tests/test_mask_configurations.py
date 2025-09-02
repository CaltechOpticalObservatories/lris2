import pytest
from slitmaskgui.mask_configurations import MaskConfigurationsWidget, CustomTableView, TableModel
from slitmaskgui.slit_position_table import SlitDisplay
import json
from unittest.mock import patch, Mock

# from unittest.mock import MagicMock
# from unittest import TestCase

MASK_NAME_1 = "name"


@pytest.fixture
def sample_config_data():
    with open('slitmaskgui/tests/testfiles/gaia_mask_config.json','r') as file:
        return json.load(file)
    
@pytest.fixture
def setup_mask_config_class(qtbot):
    config = MaskConfigurationsWidget()
    qtbot.addWidget(config)
    return config


@pytest.fixture
def setup_slit_display_class(qtbot):
    slit_display = SlitDisplay()
    slit_display.changed_data_dict = {14:2, 15:3}
    qtbot.addWidget(slit_display)
    return slit_display

#maybe add a make sure they are connected pytest fixture
def initialize_configuration(test_mask_config, sample_config_data):
    with patch.object(test_mask_config.model, 'beginResetModel'), \
         patch.object(test_mask_config.model, 'endResetModel'), \
         patch.object(test_mask_config.table, 'selectRow'):
        test_mask_config.initialize_configuration((MASK_NAME_1, sample_config_data))
    return test_mask_config


def test_initialize_configuration(setup_mask_config_class, sample_config_data):
    test_mask_config = initialize_configuration(setup_mask_config_class, sample_config_data)
    assert test_mask_config.row_to_config_dict == {0: sample_config_data}
    assert test_mask_config.model._data == [["Saved", MASK_NAME_1]]


def test_clicking_save_button_emits_signal(setup_mask_config_class, qtbot):
    test_mask_config = setup_mask_config_class
    with qtbot.waitSignal(test_mask_config.data_to_save_request) as save_button_clicked:
        test_mask_config.save_button.click()
    assert True # passed without timeout


def test_update_table_to_saved(setup_mask_config_class):
    test_mask_config = setup_mask_config_class
    test_mask_config.update_table_to_saved(0)
    assert test_mask_config.model._data[0] == ["Saved", MASK_NAME_1]



def test_data_saved_signal(setup_slit_display_class,setup_mask_config_class, sample_config_data, qtbot):
    """ This is in test mask config because it has more to do with the mask config than the slit display (data transfer) """
    test_mask_config = initialize_configuration(setup_mask_config_class, sample_config_data)
    test_slit_display = setup_slit_display_class
    test_mask_config.table = Mock()
    test_mask_config.model = Mock()
    test_mask_config.model.get_row_num = 1

    print([w["slit_width"] for w in test_mask_config.row_to_config_dict[1]])
    with qtbot.waitSignal(test_slit_display.data_changed) as bonker:
        temp_data_dict = test_slit_display.changed_data_dict
        test_slit_display.data_saved()
    assert bonker.args == [temp_data_dict]
    
    assert test_slit_display.changed_data_dict == {}  # cleared
    # assert test_mask_config.row_to_config_dict[1][15]["slit_width"] == 2  # updated
    # test_mask_config.update_table_to_saved.assert_called_once_with(0)



