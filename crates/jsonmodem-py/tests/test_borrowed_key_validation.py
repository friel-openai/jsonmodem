"""A borrowed key scan keeps conversion, errors, and callbacks unchanged."""

import dataclasses
import enum
import gc

import pytest
import jsonmodem

orjson = pytest.importorskip("orjson")

OPTIONS = (
    orjson.OPT_NON_STR_KEYS,
    orjson.OPT_NON_STR_KEYS | orjson.OPT_STRICT_INTEGER,
    orjson.OPT_NON_STR_KEYS | orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
    orjson.OPT_NON_STR_KEYS | orjson.OPT_PASSTHROUGH_SUBCLASS,
    orjson.OPT_NON_STR_KEYS | orjson.OPT_SORT_KEYS,
)


def placed(value, location):
    if location == "list":
        return [value]
    if location == "dataclass":
        @dataclasses.dataclass
        class Record:
            mapping: object

        return Record(value)
    return value


def error_signature(library, value, option, default):
    with pytest.raises(TypeError) as caught:
        library.dumps(value, option=option, default=default)
    error = caught.value
    cause = error.__cause__
    if isinstance(cause, UnicodeEncodeError):
        cause = (
            type(cause).__name__, str(cause), cause.encoding, cause.object,
            cause.start, cause.end, cause.reason,
        )
    elif cause is not None:
        cause = type(cause).__name__, str(cause)
    return type(error).__name__, str(error), cause


def late_key(kind):
    if kind == "positive-noncompact":
        return 2**30
    if kind == "negative-noncompact":
        return -(2**30)
    if kind == "unsigned-boundary":
        return 2**64 - 1
    if kind == "signed-boundary":
        return -(2**63)
    if kind == "latin1":
        return "\u00e9"
    if kind == "two-byte":
        return "\u0100"
    if kind == "four-byte":
        return "\U00010000"
    if kind == "str-subclass":
        class Key(str):
            def __str__(self):
                raise AssertionError("__str__ must not convert a key")

        return Key("last")
    if kind == "int-subclass":
        class Key(int):
            def __int__(self):
                raise AssertionError("__int__ must not convert a key")

        return Key(2048)
    if kind == "float-subclass":
        class Key(float):
            def __float__(self):
                raise AssertionError("__float__ must not convert a key")

        return Key(0.25)
    if kind == "enum":
        return enum.Enum("Key", {"item": 2048}).item
    if kind == "int-enum":
        return enum.IntEnum("Key", {"item": 2048}).item
    raise AssertionError(kind)


@pytest.mark.parametrize("option", OPTIONS)
@pytest.mark.parametrize("location", ["root", "list", "dataclass"])
def test_certified_keys_keep_escaping_boundaries_and_converted_duplicates(option, location):
    observations = []
    for library in (orjson, jsonmodem):
        value = [
            {},
            {None: 0, "null": 1, True: 2, "true": 3, False: 4, "false": 5},
            {0: 0, "0": 1, 1: 2, "1": 3, -1: 4, "-1": 5},
            {2**30 - 1: 0, -(2**30) + 1: 1},
            {2**30: 0, -(2**30): 1, 2**53: 2, 2**64 - 1: 3, -(2**63): 4},
            {0.0: 0, "0.0": 1, 1.25: 2, "1.25": 3},
            {-0.0: 0, "-0.0": 1},
            {float("inf"): 0, float("-inf"): 1, float("nan"): 2, "null": 3},
            {"": 0, "".join(map(chr, range(128))): 1},
        ]
        observations.append(library.dumps(placed(value, location), option=option))
    assert observations[0] == observations[1]


@pytest.mark.parametrize("location", ["root", "list", "dataclass"])
@pytest.mark.parametrize("invalid_key", [
    pytest.param(2**64, id="unsigned-overflow"),
    pytest.param(-(2**63) - 1, id="signed-overflow"),
    pytest.param("z\ud800", id="surrogate"),
    pytest.param(("unsupported",), id="tuple"),
    pytest.param(late_key("float-subclass"), id="float-subclass"),
])
@pytest.mark.parametrize("earlier", ["wide-value", "strict-value", "callback", "raising-callback"])
def test_late_key_errors_precede_earlier_values(location, invalid_key, earlier):
    observations = []
    for library in (orjson, jsonmodem):
        calls = []
        marker = object()
        option = library.OPT_NON_STR_KEYS
        if earlier == "wide-value":
            first_value = 2**64
        elif earlier == "strict-value":
            first_value = 2**53
            option |= library.OPT_STRICT_INTEGER
        else:
            first_value = marker

        def default(value):
            assert value is marker
            calls.append("default")
            if earlier == "raising-callback":
                raise ValueError("default failed")
            return 9

        expected = error_signature(library, {invalid_key: 0}, option, default)
        mapping = dict.fromkeys(range(1024), 0)
        mapping[0] = first_value
        mapping[invalid_key] = 1
        mapping["tail"] = marker
        actual = error_signature(library, placed(mapping, location), option, default)
        assert actual == expected
        assert calls == []
        observations.append(actual)
    assert observations[0] == observations[1]


@pytest.mark.parametrize("kind", [
    "positive-noncompact", "negative-noncompact", "unsigned-boundary", "signed-boundary",
    "latin1", "two-byte", "four-byte", "str-subclass", "int-subclass",
    "enum", "int-enum",
])
@pytest.mark.parametrize("option", OPTIONS)
@pytest.mark.parametrize("location", ["root", "dataclass"])
def test_late_refusal_keeps_bytes_and_callback_order(kind, option, location):
    observations = []
    for library in (orjson, jsonmodem):
        first, last = object(), object()
        mapping = dict.fromkeys(range(1024), 0)
        mapping[0] = first
        mapping[late_key(kind)] = 1
        mapping["tail"] = last
        calls = []

        def default(value):
            if value is first:
                calls.append("first")
                return "first value"
            assert value is last
            calls.append("last")
            return "last value"

        output = library.dumps(placed(mapping, location), option=option, default=default)
        assert calls == ["first", "last"]
        observations.append(output)
    assert observations[0] == observations[1]


@pytest.mark.parametrize("kind", ["positive-noncompact", "latin1", "str-subclass", "enum"])
@pytest.mark.parametrize("location", ["root", "dataclass"])
@pytest.mark.parametrize("earlier", ["wide-value", "strict-value", "raising-callback"])
def test_late_valid_key_preserves_the_first_value_error(kind, location, earlier):
    observations = []
    for library in (orjson, jsonmodem):
        marker = object()
        calls = []
        option = library.OPT_NON_STR_KEYS
        if earlier == "wide-value":
            first_value = 2**64
        elif earlier == "strict-value":
            first_value = 2**53
            option |= library.OPT_STRICT_INTEGER
        else:
            first_value = marker

        def default(value):
            assert value is marker
            calls.append("default")
            raise ValueError("default failed")

        expected = error_signature(library, {0: first_value}, option, default)
        calls.clear()
        mapping = dict.fromkeys(range(1024), 0)
        mapping[0] = first_value
        mapping[late_key(kind)] = 1
        actual = error_signature(library, placed(mapping, location), option, default)
        assert actual == expected
        assert calls == (["default"] if earlier == "raising-callback" else [])
        observations.append(actual)
    assert observations[0] == observations[1]


@pytest.mark.parametrize("kind", ["positive-noncompact", "latin1", "str-subclass", "enum"])
def test_callback_mutation_and_reentry_keep_the_owning_snapshot(kind):
    first, last = object(), object()
    key = late_key(kind)
    mapping = dict.fromkeys(range(1024), 0)
    mapping[0] = first
    mapping[key] = last
    expected = {**mapping, 0: "first value", key: "last value"}
    option = jsonmodem.OPT_NON_STR_KEYS
    expected_bytes = orjson.dumps(expected, option=option)
    calls = []

    def default(value):
        mapping.clear()
        gc.collect()
        assert jsonmodem.dumps({7: "inner"}, option=option) == b'{"7":"inner"}'
        if value is first:
            calls.append("first")
            return "first value"
        assert value is last
        calls.append("last")
        return "last value"

    assert jsonmodem.dumps(mapping, option=option, default=default) == expected_bytes
    assert mapping == {}
    assert calls == ["first", "last"]


@pytest.mark.parametrize("option", OPTIONS)
def test_deleted_entries_and_split_dictionary_order(option):
    observations = []
    for library in (orjson, jsonmodem):
        deleted = dict.fromkeys(range(1024), 0)
        deleted["\ud800"] = 1
        deleted[2**64] = 2
        del deleted["\ud800"], deleted[2**64]
        for key in range(0, 1024, 3):
            del deleted[key]
        deleted[-1] = 3

        class Record:
            pass

        first, second = Record(), Record()
        first.a, first.b, first.c = 1, 2, 3
        second.c, second.a = 30, 10
        del second.c
        second.b = 20
        empty = {"\ud800": 1, 2**64: 2}
        empty.clear()
        value = [deleted, vars(first), vars(second), empty]
        observations.append(library.dumps(value, option=option))
    assert observations[0] == observations[1]
