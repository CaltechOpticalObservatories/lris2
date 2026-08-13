"""Tests for camera_telemetry_shipper's RULES mapping and libby RPC reading."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

import camera_telemetry_shipper as shipper


TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _line(points, measurement):
    for point in points:
        if point._name == measurement:
            return point.to_line_protocol()
    return None


def test_module_temp():
    points = shipper.build_points({"MOD11/TEMP": "23.5"}, "lris2", TS)
    line = _line(points, "archon_module_temp")
    assert line is not None
    assert "module=MOD11" in line
    assert "temp=23.5" in line


def test_thermal_sensor():
    points = shipper.build_points({"MOD11/TEMPA": "24.1"}, "lris2", TS)
    line = _line(points, "archon_thermal_sensor")
    assert "module=MOD11" in line
    assert "sensor=A" in line
    assert "temp=24.1" in line


def test_heater_merges_output_and_pid_into_one_point():
    points = shipper.build_points(
        {
            "MOD11/HEATERAOUTPUT": "12.5",
            "MOD11/HEATERAP": "10",
            "MOD11/HEATERAI": "2",
            "MOD11/HEATERAD": "1",
        },
        "lris2",
        TS,
    )
    line = _line(points, "archon_heater")
    assert line is not None
    assert "module=MOD11" in line
    assert "heater=A" in line
    assert "output=12.5" in line
    assert "p=10i" in line
    assert "i=2i" in line
    assert "d=1i" in line


def test_vcpu_outreg():
    points = shipper.build_points({"MOD11/VCPU_OUTREG3": "7"}, "lris2", TS)
    line = _line(points, "archon_vcpu_outreg")
    assert "module=MOD11" in line
    assert "reg=3" in line
    assert "value=7i" in line


def test_unknown_key_is_dropped_not_raised():
    points = shipper.build_points({"TOTALLY_UNKNOWN_THING": "1"}, "lris2", TS)
    assert points == []


def test_hex_to_int_accepts_int_passthrough():
    assert shipper._hex_to_int(42) == 42


def test_hex_to_int_parses_hex_string():
    assert shipper._hex_to_int("1a2b3c") == 0x1A2B3C


def test_unwrap_passes_through_plain_dict():
    assert shipper._unwrap({"ok": True, "value": "x"}) == {"ok": True, "value": "x"}


def test_unwrap_extracts_resp_envelope():
    wrapped = {"resp": {"ok": True, "value": "x"}}
    assert shipper._unwrap(wrapped) == {"ok": True, "value": "x"}


def test_unwrap_non_dict_returns_empty():
    assert shipper._unwrap("not a dict") == {}


def test_read_telemetry_merges_status_and_frame():
    lib = MagicMock()
    lib.rpc.side_effect = [
        {"ok": True, "value": "BACKPLANE_TEMP=21.4"},
        {"ok": True, "value": "BUF1COMPLETE=1"},
    ]
    telemetry = shipper.read_telemetry(lib, "lris2_camera", 5.0)
    assert telemetry == {"BACKPLANE_TEMP": pytest.approx(21.4), "BUF1COMPLETE": 1}
    assert lib.rpc.call_args_list[0].args[:2] == ("lris2_camera", "status_raw")
    assert lib.rpc.call_args_list[1].args[:2] == ("lris2_camera", "frame_raw")


def test_read_telemetry_raises_on_rpc_error():
    lib = MagicMock()
    lib.rpc.return_value = {"ok": False, "error": "keyword not found"}
    with pytest.raises(shipper.TelemetryReadError):
        shipper.read_telemetry(lib, "lris2_camera", 5.0)
