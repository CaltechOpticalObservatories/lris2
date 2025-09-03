import pytest
from unittest.mock import patch, Mock
from slitmaskgui.offline_mode import InternetConnectionChecker, OfflineMode, CSUConnectionChecker


@pytest.fixture
def setup_internet_checker():
    worker = InternetConnectionChecker()
    return worker


@pytest.fixture
def setup_csu_connection_checker():
    worker = CSUConnectionChecker()
    return worker


@pytest.fixture
def setup_offline_mode():
    offline_mode = OfflineMode()
    return offline_mode


def test_offline_mode_starts_internet_connection_checker(setup_offline_mode,qtbot):
    offline_mode = setup_offline_mode

    with qtbot.waitSignal(offline_mode.offline_checker.signals.started, timeout = 2000) as worker:
        offline_mode.start_checking_internet_connection()

    assert worker.args == []


def test_worker_signals_internet_connection_connection_status(setup_offline_mode,qtbot):
    offline_mode = setup_offline_mode
    
    with qtbot.waitSignal(offline_mode.offline_checker.signals.connection_status, timeout = 2000) as worker:
        offline_mode.start_checking_internet_connection()
    
    # If connected to the internet this should be False otherwise it should be true
    assert worker.args == [False]


@pytest.mark.skip(reason="functionality is currently deleted")
def test_worker_signals_csu_connection_status(setup_offline_mode,qtbot):
    offline_mode = setup_offline_mode

    with qtbot.waitSignal(offline_mode.csu_connection_checker.signals.connection_status, timeout = 2000) as worker:
        offline_mode.check_csu_connection()

    # If connected to CSU this will == True else it will be False
    assert worker.args == [False]
