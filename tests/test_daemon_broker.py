"""Broker URL selection for LRIS2 daemons."""

import pytest
from lris2 import daemon


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (daemon.BROKER_HOST_ENV, daemon.BROKER_USER_ENV, daemon.BROKER_PASSWORD_ENV):
        monkeypatch.delenv(name, raising=False)


def test_local_broker_by_default() -> None:
    assert daemon.broker_url() == "amqp://localhost"


def test_host_and_credentials_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(daemon.BROKER_HOST_ENV, "lris2-137")
    monkeypatch.setenv(daemon.BROKER_USER_ENV, "csu")
    monkeypatch.setenv(daemon.BROKER_PASSWORD_ENV, "p@ss/word")
    assert daemon.broker_url() == "amqp://csu:p%40ss%2Fword@lris2-137"


def test_configured_url_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(daemon.BROKER_HOST_ENV, "lris2-137")
    instance = daemon.Lris2Daemon()
    instance.rabbitmq_url = "amqp://elsewhere"
    assert instance.config_rabbitmq_url() == "amqp://elsewhere"
