"""Compare callback selection, returned values, and exceptions with orjson."""

import dataclasses
import datetime
from decimal import Decimal
import enum
import pathlib
import uuid

import pytest
import jsonmodem

orjson = pytest.importorskip("orjson")


class Text(str):
    pass


class Integer(int):
    pass


class Sequence(list):
    pass


class Mapping(dict):
    pass


class Choice(enum.Enum):
    TEXT = Text("choice")


@dataclasses.dataclass
class Record:
    value: object


class Wrapped:
    def __init__(self, value):
        self.value = value


def serialize(module, option):
    calls = []

    def default(value):
        calls.append(type(value).__name__)
        if isinstance(value, Wrapped):
            return value.value
        if isinstance(value, (bytes, bytearray, memoryview)):
            return bytes(value).decode()
        if isinstance(value, (Decimal, pathlib.Path)):
            return str(value)
        if isinstance(value, set):
            return sorted(value)
        if dataclasses.is_dataclass(value):
            return {"converted": value.value}
        if isinstance(value, datetime.datetime):
            return value.isoformat()
        if isinstance(value, Text):
            return "converted text"
        if isinstance(value, Integer):
            return -int(value)
        if isinstance(value, Sequence):
            return list(value)
        if isinstance(value, Mapping):
            return dict(value)
        raise TypeError("unsupported value")

    value = {
        "z": [Wrapped(Decimal("1.234567890123456789")), Wrapped(b"binary")],
        "a": [Text("text"), Integer(4), Sequence([Text("nested")]), Mapping(x=Text("value"))],
        "m": [Record(Wrapped({1, 2})), Choice.TEXT, pathlib.Path("example")],
        "d": [datetime.datetime(2024, 1, 2, 3, 4, 5, 123456), uuid.UUID(int=7)],
        "r": [Wrapped(module.Fragment(b'{"raw":[1,2]}')), memoryview(b"view")],
    }
    return module.dumps(value, default=default, option=option), calls


@pytest.mark.parametrize("option", [
    0,
    orjson.OPT_INDENT_2,
    orjson.OPT_SORT_KEYS,
    orjson.OPT_STRICT_INTEGER,
    orjson.OPT_APPEND_NEWLINE,
    orjson.OPT_PASSTHROUGH_DATETIME,
    orjson.OPT_PASSTHROUGH_SUBCLASS,
    orjson.OPT_PASSTHROUGH_DATACLASS,
    orjson.OPT_PASSTHROUGH_DATETIME | orjson.OPT_PASSTHROUGH_SUBCLASS
    | orjson.OPT_PASSTHROUGH_DATACLASS,
    orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS | orjson.OPT_APPEND_NEWLINE
    | orjson.OPT_PASSTHROUGH_DATETIME | orjson.OPT_PASSTHROUGH_SUBCLASS
    | orjson.OPT_PASSTHROUGH_DATACLASS,
])
def test_callback_output_and_call_order(option):
    assert serialize(jsonmodem, option) == serialize(orjson, option)


@pytest.mark.parametrize("error_type", [ValueError, RuntimeError, KeyboardInterrupt])
def test_default_exception_is_preserved_as_cause(error_type):
    for module in (jsonmodem, orjson):
        error = error_type("callback failed")

        def default(value):
            raise error

        with pytest.raises(module.JSONEncodeError) as raised:
            module.dumps([object()], default=default)
        assert raised.value.__cause__ is error


def test_default_can_reenter_serializer():
    results = []
    for module in (jsonmodem, orjson):
        def default(value):
            return module.Fragment(module.dumps({"value": value.value}))

        results.append(module.dumps([Wrapped(1), Wrapped(2)], default=default))
    assert results == [b'[{"value":1},{"value":2}]'] * 2
