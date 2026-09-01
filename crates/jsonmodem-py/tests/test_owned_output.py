"""Exercise output growth, publication, and callback reentry together."""

import dataclasses
import gc

import pytest
import jsonmodem

orjson = pytest.importorskip("orjson")


@pytest.mark.parametrize("length", [0, 1, 7, 8, 255, 256, 257, 511, 512, 4096, 65536])
@pytest.mark.parametrize("option", [0, 1, 32, 1024, 1 | 32 | 1024])
def test_output_growth_and_repeated_encoded_keys(length, option):
    key = "repeat\n\"\\\x00"
    payload = [
        {key: "x" * length, "nested": [None, 1.25, True]},
        {key: "tail\n\"\\\x00", "nested": [False, -10, 42]},
    ]
    assert jsonmodem.dumps(payload, option=option) == orjson.dumps(payload, option=option)


@dataclasses.dataclass
class Record:
    payload: object
    name: str


def test_callback_reentry_keeps_each_output_private():
    retained = []

    def default(value):
        result = jsonmodem.dumps({"nested": "n" * 8192, "length": len(retained)})
        retained.append(result)
        gc.collect()
        return jsonmodem.Fragment(result)

    payload = [Record(object(), "a" * 4000), Record(object(), "b" * 10000)]
    result = jsonmodem.dumps(payload, default=default)
    expected = [
        {"payload": {"nested": "n" * 8192, "length": 0}, "name": "a" * 4000},
        {"payload": {"nested": "n" * 8192, "length": 1}, "name": "b" * 10000},
    ]
    assert result == orjson.dumps(expected)
    assert retained == [orjson.dumps(item["payload"]) for item in expected]


def test_published_bytes_do_not_change_after_later_serialization():
    first = jsonmodem.dumps({"value": "first" * 10000})
    expected = bytes(bytearray(first))
    first_hash = hash(first)
    retained = {first: "original"}
    for length in range(1000):
        jsonmodem.dumps({"other": "replacement" * length})
    gc.collect()
    assert first == expected
    assert hash(first) == first_hash
    assert retained[expected] == "original"


def test_callback_error_drops_partial_output_and_preserves_cause():
    error = RuntimeError("callback failed after output growth")

    def default(value):
        raise error

    with pytest.raises(jsonmodem.JSONEncodeError) as raised:
        jsonmodem.dumps(["prefix" * 10000, object()], default=default)
    assert raised.value.__cause__ is error
    assert jsonmodem.dumps({"after": "failure"}) == b'{"after":"failure"}'
