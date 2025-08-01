from slitmaskgui.input_targets import TargetList
import pytest

#third one should return an error, fourth one shouldn't return error but must_have wont be read
#add something to input_targets that makes it so that if one thing fails it doesn't all fail

#I just have to test the parsing 


def test_parsing():
    target_list = TargetList("slitmaskgui/tests/testfiles/star_list.txt")
    object = target_list.send_json()
    for x,index in enumerate(object):
        if index == 0:
            assert x == {"name": "Gaia_001", "ra": "15 25 32.35", "dec": "-50 46 46.8","equinox": "2000.0","vmag": "20.77","priority": "1020"}
        if index == 1:
            assert x == {"name": "Gaia_001", "ra": "15 25 32.35", "dec": "-50 46 46.8","equinox": "2000.0","vmag": "20.77","priority": "1020"}
        if index == 2:
            assert x == {"name": "UntitledStar0", "ra": "Not Provided", "dec": "Not Provided","equinox": "Not Provided","vmag": "20.77","priority": "1020"}
        if index == 3:
            assert x == {"name": "Gaia_001", "ra": "15 25 32.35", "dec": "-50 46 46.8","equinox": "2000.0","vmag": "20.77","priority": "1020"}

