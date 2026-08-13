"""Tests for CameradClient."""
from unittest.mock import MagicMock, patch

import pytest

from lris2.driver.camera_interface.cameradclient import CameradClient


@pytest.fixture
def client():
    """Creates a CameradClient instance with file logging disabled."""
    return CameradClient(log=False)


# --- value coercion / reply parsing -----------------------------------------

def test_coerce_value_int():
    assert CameradClient._coerce_value("42") == 42


def test_coerce_value_float():
    assert CameradClient._coerce_value("1.517") == pytest.approx(1.517)


def test_coerce_value_leading_zero_bitfield_stays_string():
    assert CameradClient._coerce_value("00000000") == "00000000"


def test_coerce_value_plain_string():
    assert CameradClient._coerce_value("ON") == "ON"


def test_parse_reply_extracts_key_value_pairs():
    reply = "VALID=1 COUNT=42 MOD10/XVP_V1=1.517 DINPUTS=00000000"
    values = CameradClient._parse_reply(reply)
    assert values == {
        "VALID": 1,
        "COUNT": 42,
        "MOD10/XVP_V1": pytest.approx(1.517),
        "DINPUTS": "00000000",
    }


def test_parse_reply_ignores_tokens_without_equals():
    assert CameradClient._parse_reply("DONE") == {}


# --- connect / disconnect ----------------------------------------------------

def test_connect_success(client):
    client.send_command = MagicMock(return_value="")
    client.connect("127.0.0.1", 3031)
    assert client.is_connected() is True
    client.send_command.assert_called_once_with("open")


def test_connect_open_failure_leaves_disconnected(client):
    client.send_command = MagicMock(return_value=None)
    client.connect("127.0.0.1", 3031)
    assert client.is_connected() is False


def test_connect_rejects_serial(client):
    client.send_command = MagicMock()
    client.connect("/dev/ttyS0", 9600, con_type="serial")
    assert client.is_connected() is False
    client.send_command.assert_not_called()


def test_disconnect_sends_close_when_connected(client):
    client.send_command = MagicMock(return_value="")
    client.connect("127.0.0.1", 3031)
    client.send_command.reset_mock()
    client.disconnect()
    client.send_command.assert_called_once_with("close")
    assert client.is_connected() is False


def test_disconnect_noop_when_not_connected(client):
    client.send_command = MagicMock()
    client.disconnect()
    client.send_command.assert_not_called()


# --- polling / caching --------------------------------------------------------

def test_poll_status_updates_cache_and_raw(client):
    client.send_command = MagicMock(return_value="BACKPLANE_TEMP=21.4 POWER=1")
    values = client.poll_status()
    assert values == {"BACKPLANE_TEMP": pytest.approx(21.4), "POWER": 1}
    assert client.telemetry == values
    assert client.status_raw == "BACKPLANE_TEMP=21.4 POWER=1"
    client.send_command.assert_called_once_with("native STATUS")


def test_poll_frame_updates_cache_and_raw(client):
    client.send_command = MagicMock(return_value="BUF1COMPLETE=1 TIMER=0x1a2b3c")
    values = client.poll_frame()
    assert values["BUF1COMPLETE"] == 1
    assert client.frame_raw == "BUF1COMPLETE=1 TIMER=0x1a2b3c"
    client.send_command.assert_called_once_with("native FRAME")


def test_poll_status_and_frame_merge_into_shared_cache(client):
    client.send_command = MagicMock(side_effect=["POWER=1", "BUF1COMPLETE=1"])
    client.poll_status()
    client.poll_frame()
    assert client.telemetry == {"POWER": 1, "BUF1COMPLETE": 1}


def test_poll_status_raises_on_command_failure(client):
    client.send_command = MagicMock(return_value=None)
    with pytest.raises(IOError):
        client.poll_status()


def test_get_atomic_value_returns_cached_value(client):
    client.send_command = MagicMock(return_value="BACKPLANE_TEMP=21.4")
    client.poll_status()
    assert client.get_atomic_value("BACKPLANE_TEMP") == pytest.approx(21.4)


def test_get_atomic_value_unknown_key_returns_none(client):
    assert client.get_atomic_value("NOPE") is None


# --- wire protocol (socket framing) ------------------------------------------

def _fake_socket(chunks):
    sock = MagicMock()
    sock.recv.side_effect = chunks
    return sock


def test_send_command_reads_multi_chunk_reply_until_done(client):
    client.host, client.port = "127.0.0.1", 3031
    client._set_connected(True)
    fake_sock = _fake_socket([b"BACKPLANE_TEMP=21.4 ", b"POWER=1 ", b"DONE"])
    with patch("socket.create_connection", return_value=fake_sock) as mock_conn:
        reply = client.send_command("native STATUS")
    mock_conn.assert_called_once_with(("127.0.0.1", 3031), timeout=client.timeout)
    fake_sock.sendall.assert_called_once_with(b"native STATUS\n")
    assert reply == "BACKPLANE_TEMP=21.4 POWER=1"
    fake_sock.close.assert_called_once()


def test_send_command_returns_none_on_error_reply(client):
    client.host, client.port = "127.0.0.1", 3031
    client._set_connected(True)
    fake_sock = _fake_socket([b"ERROR"])
    with patch("socket.create_connection", return_value=fake_sock):
        reply = client.send_command("native BOGUS")
    assert reply is None


def test_send_command_when_not_connected_returns_none(client):
    with patch("socket.create_connection") as mock_conn:
        reply = client.send_command("native STATUS")
    assert reply is None
    mock_conn.assert_not_called()
