import pytest
from unittest.mock import patch, Mock
from slitmaskgui.connection_checkers import InternetConnectionChecker, ThreadPool, OfflineMode, CSUConnectionChecker


@pytest.fixture
def setup_internet_checker():
    worker = InternetConnectionChecker()
    return worker


@pytest.fixture
def setup_csu_connection_checker():
    worker = CSUConnectionChecker()
    return worker


@pytest.fixture
def setup_threadpool(setup_internet_checker, setup_csu_connection_checker):
    threadpool = ThreadPool()
    threadpool.offline_checker = setup_internet_checker
    threadpool.csu_connection_checker = setup_csu_connection_checker
    return threadpool


@pytest.fixture
def setup_offline_mode(setup_threadpool):
    offline_mode = OfflineMode()
    offline_mode.threadpool = setup_threadpool
    return offline_mode


def test_threadpool_starts_internet_connection_checker(setup_threadpool,qtbot):
    threadpool = setup_threadpool

    with qtbot.waitSignal(threadpool.offline_checker.signals.started, timeout = 2000) as worker:
        threadpool.start_internet_connection_checker()

    assert worker.args == []


def test_worker_signals_internet_connection_connection_status(setup_offline_mode,qtbot):
    offline_mode = setup_offline_mode
    
    with qtbot.waitSignal(offline_mode.threadpool.offline_checker.signals.connection_status, timeout = 2000) as worker:
        offline_mode.start_checking_internet_connection()
    
    # If connected to the internet this should be False otherwise it should be true
    assert worker.args == [False]


def test_worker_signals_csu_connection_status(setup_offline_mode,qtbot):
    offline_mode = setup_offline_mode

    with qtbot.waitSignal(offline_mode.threadpool.csu_connection_checker.signals.connection_status, timeout = 2000) as worker:
        offline_mode.check_csu_connection()

    # If connected to CSU this will == True else it will be False
    assert worker.args == [False]
