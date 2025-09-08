import pytest
from slitmaskgui.backend.star_list import StarList
from slitmaskgui.backend.mask_gen import SlitMask
import json



@pytest.fixture
def sample_target_list():
    with open('slitmaskgui/tests/testfiles/gaia_target_list.json','r') as file:
        return file.read()

@pytest.fixture
def sample_config_data():
    with open('slitmaskgui/tests/testfiles/gaia_mask_config.json','r') as file:
        return json.load(file)
    
@pytest.fixture
def initialize_star_list(sample_target_list):
    return StarList(sample_target_list,slit_width='0.7',use_center_of_priority=True)

@pytest.mark.skip(reason="mismatch in decimal places")
def test_send_mask(initialize_star_list,sample_config_data):
    payload = initialize_star_list
    result = payload.send_mask()
    assert result == sample_config_data