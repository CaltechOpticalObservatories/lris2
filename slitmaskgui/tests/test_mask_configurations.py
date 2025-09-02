import pytest
from slitmaskgui.mask_configurations import MaskConfigurationsWidget, CustomTableView, TableModel
import json
from unittest.mock import patch

# from unittest.mock import MagicMock
# from unittest import TestCase

@pytest.fixture()
def sample_config_data():
    with open('slitmaskgui/tests/testfiles/gaia_mask_config.json','r') as file:
        return json.load(file)
    
@pytest.fixture()
def setup_mask_config_class(qtbot):
    config = MaskConfigurationsWidget()
    qtbot.addWidget(config)
    return config

#maybe add a make sure they are connected pytest fixture

def test_initialize_configuration(setup_mask_config_class,sample_config_data):
    test_config_widget = setup_mask_config_class
    global name
    name = "name"

    with patch.object(test_config_widget.model, 'beginResetModel'), \
         patch.object(test_config_widget.model, 'endResetModel'), \
         patch.object(test_config_widget.table, 'selectRow'):
        
        test_config_widget.initialize_configuration((name, sample_config_data))

    assert test_config_widget.row_to_config_dict == {0:sample_config_data}
    assert test_config_widget.model._data == [["Saved", name]]


def test_clicking_save_button_emits_signal(setup_mask_config_class, qtbot):
    test_config_widget = setup_mask_config_class

    with qtbot.waitSignal(test_config_widget.data_to_save_request) as save_button_clicked:
        test_config_widget.save_button.click()
    assert True # passed without timeout


def test_update_table_to_saved(setup_mask_config_class):
    test_config_widget = setup_mask_config_class

    test_config_widget.update_table_to_saved(0)

    assert test_config_widget.model._data[0] == ["Saved", name]



