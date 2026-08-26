"""Check direct bytes construction and the escaped-string fallback."""

import json

import pytest

import jsonmodem


@pytest.mark.parametrize("length", [0, 1, 255, 256, 257, 4096, 131072])
@pytest.mark.parametrize("text", ["x", "\u00e9", "\u2603", "\U0001f600"])
@pytest.mark.parametrize("option", [0, 1, 1024, 1025])
def test_root_string_bytes(length, text, option):
    value = text * length
    expected = json.dumps(value, ensure_ascii=False).encode()
    if option & 1024:
        expected += b"\n"
    assert jsonmodem.dumps(value, option=option) == expected


@pytest.mark.parametrize("length", [0, 255, 256, 4096, 131072])
@pytest.mark.parametrize("escape", ['"', "\\", "\n", "\x00", "\x1f"])
def test_root_string_escapes(length, escape):
    for value in (escape + "x" * length, "x" * length + escape):
        assert jsonmodem.dumps(value) == json.dumps(value).encode()


@pytest.mark.parametrize("value", ["\ud800", "x" * 4096 + "\udfff"])
def test_invalid_root_surrogates(value):
    with pytest.raises(TypeError, match="UTF-8"):
        jsonmodem.dumps(value)
