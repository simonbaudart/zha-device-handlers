"""Test units for new Tuya cluster framework."""

from unittest import mock

import pytest
import zigpy.zcl.foundation as zcl_f

from zhaquirks.tuya import (
    TUYA_ACTIVE_STATUS_RPT,
    TUYA_GET_DATA,
    TUYA_SET_DATA_RESPONSE,
    TUYA_SET_TIME,
    TuyaCommand,
    TuyaData,
    TuyaNewManufCluster,
)


@pytest.fixture(name="TuyaCluster")
def tuya_cluster(zigpy_device_mock):
    """Mock of the new Tuya manufacturer cluster."""
    device = zigpy_device_mock()
    endpoint = device.add_endpoint(1)
    cluster = TuyaNewManufCluster(endpoint)
    return cluster


def test_tuya_data_value():
    """Test tuya "Value" datatype."""

    data = b"\x02\x00\x04\x00\x00\x02\xdb"
    extra = b"extra data"

    r, rest = TuyaData.deserialize(data + extra)
    assert rest == extra

    assert r.dp_type == 2
    assert r.raw == b"\xdb\x02\x00\x00"
    assert r.payload == 731


def test_tuya_data_bool():
    """Test tuya Bool datatype."""

    data = b"\x01\x00\x01\x00"
    extra = b"extra data"

    r, rest = TuyaData.deserialize(data + extra)
    assert rest == extra

    assert r.dp_type == 1
    assert r.raw == b"\x00"
    assert not r.payload

    data = b"\x01\x00\x01\x01"
    extra = b"extra data"

    r, rest = TuyaData.deserialize(data + extra)
    assert rest == extra

    assert r.dp_type == 1
    assert r.raw == b"\x01"
    assert r.payload


def test_tuya_data_enum():
    """Test tuya Enum datatype."""

    data = b"\x04\x00\x01\x40"
    extra = b"extra data"

    r, rest = TuyaData.deserialize(data + extra)
    assert rest == extra

    assert r.dp_type == 4
    assert r.raw == b"\x40"
    assert r.payload == 0x40


def test_tuya_data_string():
    """Test tuya String datatype."""

    data = b"\x03\x00\x04Tuya"
    extra = b"extra data"

    r, rest = TuyaData.deserialize(data + extra)
    assert rest == extra

    assert r.dp_type == 3
    assert r.raw == b"Tuya"
    assert r.payload == "Tuya"


def test_tuya_data_bitmap():
    """Test tuya Bitmap datatype."""

    data = b"\x05\x00\x01\x40"
    extra = b"extra data"

    r, rest = TuyaData.deserialize(data + extra)
    assert rest == extra

    assert r.dp_type == 5
    assert r.raw == b"\x40"
    assert r.payload == 0x40

    data = b"\x05\x00\x02\x40\x02"
    r, _ = TuyaData.deserialize(data)
    r.payload == 0x4002

    data = b"\x05\x00\x04\x40\x02\x80\x01"
    r, _ = TuyaData.deserialize(data)
    r.payload == 0x40028001


def test_tuya_data_bitmap_invalid():
    """Test tuya Bitmap datatype."""

    data = b"\x05\x00\x03\x4012"
    extra = b"extra data"

    r, rest = TuyaData.deserialize(data + extra)
    assert rest == extra

    with pytest.raises(ValueError):
        r.payload


@pytest.mark.parametrize(
    "cmd_id, handler_name, args",
    (
        (
            TUYA_GET_DATA,
            "handle_get_data",
            (TuyaCommand(0, 2, 2, TuyaData(1, 0, b"\x01\x01")),),
        ),
        (
            TUYA_SET_DATA_RESPONSE,
            "handle_set_data_response",
            (TuyaCommand(0, 2, 2, TuyaData(1, 0, b"\x01\x01")),),
        ),
        (
            TUYA_ACTIVE_STATUS_RPT,
            "handle_active_status_report",
            (TuyaCommand(0, 2, 2, TuyaData(1, 0, b"\x01\x01")),),
        ),
        (TUYA_SET_TIME, "handle_set_time_request", (0x1234,)),
    ),
)
@mock.patch("zhaquirks.tuya.TuyaNewManufCluster.send_default_rsp")
def test_tuya_cluster_request(
    default_rsp_mock, cmd_id, handler_name, args, TuyaCluster
):
    """Test cluster specific request."""

    hdr = zcl_f.ZCLHeader.general(1, cmd_id, is_reply=True)
    hdr.frame_control.disable_default_response = False

    with mock.patch.object(TuyaCluster, handler_name) as handler:
        handler.return_value = mock.sentinel.status
        TuyaCluster.handle_cluster_request(hdr, args)
        assert handler.call_count == 1
        assert default_rsp_mock.call_count == 1
        assert default_rsp_mock.call_args[1]["status"] is mock.sentinel.status


@mock.patch("zhaquirks.tuya.TuyaNewManufCluster.send_default_rsp")
def test_tuya_cluster_request_unk_command(default_rsp_mock, TuyaCluster):
    """Test cluster specific request handler -- no handler."""

    hdr = zcl_f.ZCLHeader.general(1, 0xFE, is_reply=True)
    hdr.frame_control.disable_default_response = False

    TuyaCluster.handle_cluster_request(hdr, (mock.sentinel.args,))
    assert default_rsp_mock.call_count == 1
    assert default_rsp_mock.call_args[1]["status"] == zcl_f.Status.UNSUP_CLUSTER_COMMAND


@mock.patch("zhaquirks.tuya.TuyaNewManufCluster.send_default_rsp")
def test_tuya_cluster_request_no_handler(default_rsp_mock, TuyaCluster):
    """Test cluster specific request handler -- no handler."""

    hdr = zcl_f.ZCLHeader.general(1, 0xFE, is_reply=True)
    hdr.frame_control.disable_default_response = False

    new_client_commands = TuyaCluster.client_commands.copy()
    new_client_commands[0xFE] = zcl_f.ZCLCommandDef(
        "no_such_handler", {}, is_manufacturer_specific=True
    )

    with mock.patch.object(TuyaCluster, "client_commands", new_client_commands):
        TuyaCluster.handle_cluster_request(hdr, (mock.sentinel.args,))

    assert default_rsp_mock.call_count == 1
    assert default_rsp_mock.call_args[1]["status"] == zcl_f.Status.UNSUP_CLUSTER_COMMAND
