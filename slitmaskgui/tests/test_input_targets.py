from slitmaskgui.backend.input_targets import TargetList
import pytest
import json

@pytest.fixture
def sample_target_list():
    with open('slitmaskgui/tests/testfiles/gaia_target_list.json','r') as file:
        return json.load(file)

def test_parsing(sample_target_list):
    target_list = TargetList("slitmaskgui/tests/testfiles/gaia_starlist.txt")
    object = target_list.send_json()
    for star_item in json.loads(object):
        assert star_item in sample_target_list
