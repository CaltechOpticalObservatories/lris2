"""Broker URL selection for LRIS2 daemons."""

import pytest
from libby.config_resolve import RABBITMQ_URL_ENV
from lris2.daemon import Lris2Daemon


def test_environment_wins_over_the_daemon_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(RABBITMQ_URL_ENV, "amqp://lris2-137")
    instance = Lris2Daemon()
    instance.rabbitmq_url = "amqp://elsewhere"
    assert instance.config_rabbitmq_url() == "amqp://lris2-137"


def test_local_broker_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(RABBITMQ_URL_ENV, raising=False)
    assert Lris2Daemon().config_rabbitmq_url() == "amqp://localhost"
