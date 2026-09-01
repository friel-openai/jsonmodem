"""Exercise output growth, publication, and callback reentry together."""

import dataclasses
import gc

import pytest
import jsonmodem

orjson = pytest.importorskip("orjson")


@dataclasses.dataclass
class Record:
    payload: object
    name: str


def output_input(payload, entry):
    """Keep ordinary JSON as a control, or force the callback-aware encoder."""
    if entry == "plain":
        return payload, {}
    if entry == "dataclass":
        return Record(payload, ""), {}
    assert entry == "default"
    marker = object()

    def default(value):
        assert value is marker
        return payload

    # Supplying default with ordinary JSON would still use the basic encoder.
    return marker, {"default": default}


@pytest.mark.parametrize("entry", ["plain", "dataclass", "default"])
@pytest.mark.parametrize("length", [0, 1, 7, 8, 255, 256, 257, 511, 512, 4096, 65536])
@pytest.mark.parametrize("option", [0, 1, 32, 1024, 1 | 32 | 1024])
def test_output_growth_and_repeated_encoded_keys(length, option, entry):
    key = "repeat\n\"\\\x00"
    payload = [
        {key: "x" * length, "nested": [None, 1.25, True]},
        {key: "tail\n\"\\\x00", "nested": [False, -10, 42]},
    ]
    value, kwargs = output_input(payload, entry)
    assert jsonmodem.dumps(value, option=option, **kwargs) == orjson.dumps(
        value, option=option, **kwargs
    )


@pytest.mark.parametrize("entry", ["dataclass", "default"])
@pytest.mark.parametrize("length", [255, 256, 257])
@pytest.mark.parametrize("option", [0, 1, 32, 1024, 1 | 32 | 1024])
def test_callback_output_at_growth_boundary(length, option, entry):
    empty, kwargs = output_input("", entry)
    overhead = len(orjson.dumps(empty, option=option, **kwargs))
    value, kwargs = output_input("x" * (length - overhead), entry)
    expected = orjson.dumps(value, option=option, **kwargs)
    assert len(expected) == length

    result = jsonmodem.dumps(value, option=option, **kwargs)
    result_hash = hash(result)
    assert type(result) is bytes
    assert len(result) == length
    assert result == expected

    replacement, kwargs = output_input("replacement" * 65536, entry)
    jsonmodem.dumps(replacement, option=option, **kwargs)
    gc.collect()
    assert result == expected
    assert hash(result) == result_hash


@pytest.mark.parametrize("entry", ["plain", "dataclass", "default"])
def test_callback_reentry_keeps_each_output_private(entry):
    retained = []
    expected_retained = []
    for length in range(2):
        value, kwargs = output_input({"nested": "n" * 8192, "length": length}, entry)
        expected_retained.append(orjson.dumps(value, **kwargs))

    def default(value):
        nested, kwargs = output_input(
            {"nested": "n" * 8192, "length": len(retained)}, entry
        )
        result = jsonmodem.dumps(nested, **kwargs)
        retained.append(result)
        gc.collect()
        return jsonmodem.Fragment(result)

    payload = [Record(object(), "a" * 4000), Record(object(), "b" * 10000)]
    result = jsonmodem.dumps(payload, default=default)
    expected = [
        {"payload": orjson.loads(expected_retained[0]), "name": "a" * 4000},
        {"payload": orjson.loads(expected_retained[1]), "name": "b" * 10000},
    ]
    assert result == orjson.dumps(expected)
    assert retained == expected_retained


@pytest.mark.parametrize("entry", ["plain", "dataclass", "default"])
def test_published_bytes_do_not_change_after_later_serialization(entry):
    value, kwargs = output_input({"value": "first" * 10000}, entry)
    first = jsonmodem.dumps(value, **kwargs)
    expected = orjson.dumps(value, **kwargs)
    assert first == expected
    first_hash = hash(first)
    retained = {first: "original"}
    for length in range(1000):
        value, kwargs = output_input({"other": "replacement" * length}, entry)
        jsonmodem.dumps(value, **kwargs)
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
