"""Decoded arrays retain their values across growth, errors and input release."""

import array
import gc
import json
import struct

import jsonmodem
import pytest

try:
    import orjson
except ModuleNotFoundError as error:
    if error.name != "orjson":
        raise
    orjson = None


LENGTHS = (0, 1, 2, 3, 4, 5, 7, 8, 9, 15, 16, 17, 24, 25, 32, 33, 40, 41,
           52, 53, 64, 65, 76, 77, 128, 129, 256, 257, 1024)
PATTERNS = ("integers", "floats", "strings", "lists", "objects", "mixed", "limits")
INPUTS = ("bytes", "str", "bytearray", "memoryview", "array_view")


def values(pattern, length):
    if pattern == "integers":
        return [10000 + index for index in range(length)]
    if pattern == "floats":
        return [-0.0 if index % 2 == 0 else index / 7 for index in range(length)]
    if pattern == "strings":
        return [f"value-{index}-\u00e9-\u2603-\U0001f642\n\0" for index in range(length)]
    if pattern == "lists":
        return [[index, [index + 10000]] for index in range(length)]
    if pattern == "objects":
        return [{"index": index, "values": [index + 10000]} for index in range(length)]
    if pattern == "mixed":
        choices = (None, True, False, -0.0, 10000, "text\n", [], {}, [1], {"a": [2]})
    else:
        assert pattern == "limits"
        choices = (-(2**63), -1, 0, 2**53 + 1, 2**63, 2**64 - 1, 2**64, 1e-300, 1e300)
    return [choices[index % len(choices)] for index in range(length)]


def as_input(raw, kind):
    if kind == "bytes":
        return raw
    if kind == "str":
        return raw.decode("utf-8")
    if kind == "bytearray":
        return bytearray(raw)
    if kind == "memoryview":
        return memoryview(bytearray(raw))
    assert kind == "array_view"
    return memoryview(array.array("B", raw))


def assert_same(actual, expected):
    assert type(actual) is type(expected)
    if type(expected) is float:
        assert struct.pack("!d", actual) == struct.pack("!d", expected)
    elif type(expected) is list:
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected):
            assert_same(left, right)
    elif type(expected) is dict:
        assert list(actual) == list(expected)
        for key in expected:
            assert_same(actual[key], expected[key])
    else:
        assert actual == expected


def parse_integer(token):
    value = int(token)
    if -(2**63) <= value <= 2**64 - 1:
        return value
    # The fixtures contain one value above the unsigned 64-bit maximum.
    assert value == 2**64
    return float(value)


@pytest.mark.parametrize("length", LENGTHS)
@pytest.mark.parametrize("pattern", PATTERNS)
@pytest.mark.parametrize("kind", INPUTS)
def test_array_values_across_growth_boundaries(length, pattern, kind):
    raw = json.dumps(values(pattern, length), ensure_ascii=False, separators=(",", ":")).encode()
    expected = json.loads(raw, parse_int=parse_integer)
    if orjson is not None:
        assert_same(orjson.loads(as_input(raw, kind)), expected)
    actual = jsonmodem.loads(as_input(raw, kind))
    assert_same(actual, expected)
    gc.collect()
    assert_same(actual, expected)


@pytest.mark.parametrize("length", (2, 5, 17, 65, 257))
@pytest.mark.parametrize("nested", (False, True))
def test_decoded_children_do_not_share_mutable_storage(length, nested):
    item = {"items": []} if nested else []
    raw = json.dumps([item] * length, separators=(",", ":")).encode()
    codecs = (jsonmodem,) if orjson is None else (orjson, jsonmodem)
    for codec in codecs:
        actual = codec.loads(raw)
        assert len({id(child) for child in actual}) == length
        if nested:
            assert len({id(child["items"]) for child in actual}) == length
            actual[0]["items"].append("changed")
            assert all(child["items"] == [] for child in actual[1:])
        else:
            actual[0].append("changed")
            assert all(child == [] for child in actual[1:])


@pytest.mark.parametrize("kind", ("bytearray", "memoryview", "array_view"))
def test_array_values_survive_mutating_and_releasing_input(kind):
    raw = b'[[10000,"owned text"],{"items":[20000,"other text"]}]'
    expected = json.loads(raw, parse_int=parse_integer)
    if orjson is not None:
        assert_same(orjson.loads(raw), expected)
    source = as_input(raw, kind)
    actual = jsonmodem.loads(source)
    source[:] = b" " * len(source)
    if isinstance(source, memoryview):
        source.release()
    del source
    gc.collect()
    assert_same(actual, expected)


def live_marker_lists():
    # No Python fixture list contains this prefix. A match belongs to a decode.
    return sum(
        type(value) is list
        and bool(value)
        and type(value[0]) is str
        and value[0] == "owned-append-cleanup-marker"
        for value in gc.get_objects()
    )


@pytest.mark.parametrize("length", (1, 5, 17, 65, 257))
@pytest.mark.parametrize("tail", (b"!", b"1e400", b'"\\uD800"', b"[1,]"))
def test_array_owners_are_released_after_error(length, tail):
    raw = b'["owned-append-cleanup-marker",' + b'{"items":[10000]},' * length + tail + b"]"
    gc.collect()
    before = live_marker_lists()
    for _ in range(3):
        with pytest.raises(jsonmodem.JSONDecodeError) as error:
            jsonmodem.loads(raw)
        assert error.value.doc == raw.decode()
        del error
        gc.collect()
        assert live_marker_lists() == before
        assert jsonmodem.loads(b"[10000,20000]") == [10000, 20000]


def test_array_owners_are_released_after_success():
    gc.collect()
    before = live_marker_lists()
    result = jsonmodem.loads(b'["owned-append-cleanup-marker",[10000],{"a":20000}]')
    assert live_marker_lists() == before + 1
    del result
    gc.collect()
    assert live_marker_lists() == before
