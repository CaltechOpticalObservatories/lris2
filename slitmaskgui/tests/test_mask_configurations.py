import pytest
from slitmaskgui.mask_configurations import MaskConfigurationsWidget, CustomTableView, TableModel
import json
# from unittest.mock import MagicMock
# from unittest import TestCase

@pytest.fixture
def sample_config_data():
    with open('slitmaskgui/tests/testfiles/gaia_mask_config.json','r') as file:
        return json.load(file)
    
@pytest.fixture
def setup_mask_config_class(qtbot):
    config = MaskConfigurationsWidget()
    qtbot.addWidget(config)
    return config

# @pytest.mark.slow
def test_initialize_configuration(setup_mask_config_class,sample_config_data):
    test_config_widget = setup_mask_config_class
    name = "name"
    test_config_widget.initialize_configuration((name,sample_config_data))

    assert test_config_widget.row_to_config_dict == {0:sample_config_data}
    assert test_config_widget.model._data == [["Saved", name]]





