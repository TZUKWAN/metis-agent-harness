"""Tests for MCP JSON-RPC protocol utilities."""

import json

import pytest

from metis.mcp.protocol import (
    decode_message,
    encode_message,
    make_error,
    make_notification,
    make_request,
    make_response,
)


def test_make_request_builds_valid_json_rpc():
    req = make_request("tools/list", {"foo": "bar"}, request_id=42)

    assert req["jsonrpc"] == "2.0"
    assert req["method"] == "tools/list"
    assert req["params"] == {"foo": "bar"}
    assert req["id"] == 42


def test_make_request_omits_id_when_none():
    req = make_request("initialize", {}, request_id=None)

    assert "id" not in req


def test_make_response_builds_valid_json_rpc():
    resp = make_response(42, {"tools": []})

    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 42
    assert resp["result"] == {"tools": []}


def test_make_error_builds_valid_json_rpc():
    err = make_error(42, -32600, "Invalid request")

    assert err["jsonrpc"] == "2.0"
    assert err["id"] == 42
    assert err["error"]["code"] == -32600
    assert err["error"]["message"] == "Invalid request"


def test_make_error_includes_null_id():
    err = make_error(None, -32700, "Parse error")

    assert err["jsonrpc"] == "2.0"
    assert err["id"] is None
    assert err["error"]["code"] == -32700


def test_make_notification_builds_valid_json_rpc():
    note = make_notification("notifications/initialized")

    assert note["jsonrpc"] == "2.0"
    assert note["method"] == "notifications/initialized"
    assert "id" not in note


def test_encode_message_serializes_to_json_line():
    payload = {"jsonrpc": "2.0", "id": 1, "result": {}}
    encoded = encode_message(payload)

    assert encoded == '{"jsonrpc": "2.0", "id": 1, "result": {}}\n'
    assert json.loads(encoded.strip()) == payload


def test_decode_message_parses_json_line():
    raw = '{"jsonrpc": "2.0", "id": 1, "result": {}}'
    decoded = decode_message(raw)

    assert decoded == {"jsonrpc": "2.0", "id": 1, "result": {}}


def test_decode_message_parses_without_jsonrpc_check():
    result = decode_message('{"id": 1}')
    assert result == {"id": 1}


def test_decode_message_raises_on_malformed_json():
    with pytest.raises((ValueError, json.JSONDecodeError)):
        decode_message('{not}')
