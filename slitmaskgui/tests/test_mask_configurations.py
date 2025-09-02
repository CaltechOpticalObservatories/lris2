import pytest
from slitmaskgui.mask_configurations import MaskConfigurationsWidget, CustomTableView, TableModel
from slitmaskgui.slit_position_table import SlitDisplay
import json
from unittest.mock import patch, Mock

""" To test the connections between the classes we will test app.py"""

MASK_NAME_1 = "name"
MASK_NAME_2 = "other_name"


@pytest.fixture
def sample_config_data():
    with open('slitmaskgui/tests/testfiles/gaia_mask_config.json','r') as file:
        return json.load(file)
    
@pytest.fixture
def setup_mask_config_class(qtbot):
    config = MaskConfigurationsWidget()
    qtbot.addWidget(config)
    return config


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


# def test_switching_masks()


# def test_export_button()


# def test_export_all_button()


# def test_close_button()


# def test_open_button()





