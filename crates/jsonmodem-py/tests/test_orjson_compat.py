import dataclasses
import datetime
import math
import uuid

import pytest

import jsonmodem


@pytest.mark.parametrize(
    "document,value",
    [
        (b"null", None),
        (b"true", True),
        (b"false", False),
        (b"0", 0),
        (b"-0", 0),
        (b"1.25e2", 125.0),
        (b'"snowman: \\u2603"', "snowman: ☃"),
        (b'[1,{"x":null}]', [1, {"x": None}]),
    ],
)
def test_loads_common_values(document, value):
    assert jsonmodem.loads(document) == value


def test_loads_preserves_integer_precision_and_duplicate_key_semantics():
    value = 2**100 + 123
    assert jsonmodem.loads(str(value)) == value
    assert jsonmodem.loads(b'{"x":1,"x":2}') == {"x": 2}


@pytest.mark.parametrize(
    "document",
    [b"", b"[", b"[1,]", b'{"x" 1}', b"01", b"NaN", b"Infinity", b"1e400", b'"\\ud800"'],
)
def test_loads_rejects_invalid_json(document):
    with pytest.raises(jsonmodem.JSONDecodeError):
        jsonmodem.loads(document)


def test_loads_rejects_invalid_utf8_as_decode_error():
    with pytest.raises(jsonmodem.JSONDecodeError):
        jsonmodem.loads(b'"\xff"')


def test_loads_accepts_supported_input_types():
    assert jsonmodem.loads("[1]") == [1]
    assert jsonmodem.loads(bytearray(b"[1]")) == [1]
    assert jsonmodem.loads(memoryview(b"[1]")) == [1]
    with pytest.raises(TypeError):
        jsonmodem.loads(1)


def test_loads_depth_is_bounded():
    jsonmodem.loads("[" * 256 + "]" * 256)
    with pytest.raises(jsonmodem.JSONDecodeError, match="recursion depth"):
        jsonmodem.loads("[" * 257 + "]" * 257)


def test_dumps_common_values_and_non_finite_floats():
    assert jsonmodem.dumps({"a": [1, True, None, "☃"]}) == (
        b'{"a":[1,true,null,"\xe2\x98\x83"]}'
    )
    assert jsonmodem.dumps([math.nan, math.inf, -math.inf]) == b"[null,null,null]"


def test_dumps_default_and_passthrough_subclass():
    class Secret(str):
        pass

    assert jsonmodem.dumps(
        {"secret": Secret("token")},
        default=lambda _: "[redacted]",
        option=jsonmodem.OPT_PASSTHROUGH_SUBCLASS,
    ) == b'{"secret":"[redacted]"}'
    assert jsonmodem.dumps(Secret("token")) == b'"token"'


def test_dumps_options():
    option = jsonmodem.OPT_SORT_KEYS | jsonmodem.OPT_APPEND_NEWLINE
    assert jsonmodem.dumps({"b": 1, "a": 2}, option=option) == b'{"a":2,"b":1}\n'
    assert jsonmodem.dumps({None: 1}, option=jsonmodem.OPT_NON_STR_KEYS) == b'{"null":1}'
    with pytest.raises(jsonmodem.JSONEncodeError):
        jsonmodem.dumps(2**53, option=jsonmodem.OPT_STRICT_INTEGER)


def test_dumps_datetime_uuid_dataclass_and_fragment():
    @dataclasses.dataclass
    class Item:
        name: str

    value = {
        "at": datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
        "id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
        "item": Item("x"),
        "raw": jsonmodem.Fragment(b'{"duplicate":1,"duplicate":2}'),
    }
    encoded = jsonmodem.dumps(value, option=jsonmodem.OPT_UTC_Z)
    assert b'"at":"2026-01-02T00:00:00Z"' in encoded
    assert b'"id":"00000000-0000-0000-0000-000000000001"' in encoded
    assert b'"item":{"name":"x"}' in encoded
    assert b'"raw":{"duplicate":1,"duplicate":2}' in encoded


def test_dumps_rejects_cycles_excess_depth_and_unknown_options():
    value = []
    value.append(value)
    with pytest.raises(jsonmodem.JSONEncodeError):
        jsonmodem.dumps(value)

    nested = None
    for _ in range(257):
        nested = [nested]
    with pytest.raises(jsonmodem.JSONEncodeError, match="recursion depth"):
        jsonmodem.dumps(nested)

    with pytest.raises(jsonmodem.JSONEncodeError, match="unsupported option"):
        jsonmodem.dumps({}, option=1 << 30)
