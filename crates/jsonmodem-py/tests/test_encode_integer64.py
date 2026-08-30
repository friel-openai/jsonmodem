"""Preserve integer encoding while copying CPython's initialized digits."""

from dataclasses import dataclass
from enum import IntEnum
import gc
import json
import random

import pytest

import jsonmodem


def integer_boundaries():
    values = {-5, -1, 0, 1, 256, 257}
    for bits in (14, 15, 16, 29, 30, 31, 52, 53, 54, 59, 60, 61, 62, 63, 64):
        for delta in (-1, 0, 1):
            values.add(2**bits + delta)
            values.add(-(2**bits + delta))
    for high in (1, 7, 8, 15):
        for low in (0, 1, 2**30 - 1, 2**30, 2**60 - 1):
            magnitude = high * 2**60 + low
            values.add(magnitude)
            values.add(-magnitude)
    return sorted(value for value in values if -(2**63) <= value < 2**64)


VALUES = integer_boundaries()
WIDE_VALUES = [-(2**63), -(2**60), 2**30, 2**53 - 1, 2**60, 2**63, 2**64 - 1]


@pytest.fixture(params=["jsonmodem", "orjson"])
def library(request):
    return jsonmodem if request.param == "jsonmodem" else pytest.importorskip("orjson")


def fresh_integer(value, construction="bytes"):
    if construction == "decimal":
        return int(str(value))
    if construction == "arithmetic":
        return (value * 3 + 1 - 1) // 3
    size = max(1, (value.bit_length() + 8) // 8)
    return int.from_bytes(value.to_bytes(size, "little", signed=True), "little", signed=True)


def reference_bytes(value, *, indent=False, newline=False, sort_keys=False):
    if indent:
        encoded = json.dumps(value, indent=2, sort_keys=sort_keys).encode()
    else:
        encoded = json.dumps(value, separators=(",", ":"), sort_keys=sort_keys).encode()
    return encoded + (b"\n" if newline else b"")


@pytest.mark.parametrize("value", VALUES)
@pytest.mark.parametrize("construction", ["bytes", "decimal", "arithmetic"])
def test_integer_storage_values(library, value, construction):
    integer = fresh_integer(value, construction)
    assert type(integer) is int
    assert integer == value
    expected = str(value).encode()
    assert library.dumps(integer) == expected
    for container in ([integer, integer], (integer,), {"value": integer}):
        assert library.dumps(container) == reference_bytes(container)


@pytest.mark.parametrize("value", WIDE_VALUES)
@pytest.mark.parametrize("indent", [False, True])
@pytest.mark.parametrize("newline", [False, True])
def test_integer_storage_options(library, value, indent, newline):
    option = (library.OPT_INDENT_2 if indent else 0) | (library.OPT_APPEND_NEWLINE if newline else 0)
    integer = fresh_integer(value)
    values = {"z": [integer, integer], "a": (integer,)}
    option |= library.OPT_SORT_KEYS
    assert library.dumps(values, option=option) == reference_bytes(
        values, indent=indent, newline=newline, sort_keys=True
    )


@pytest.mark.parametrize("value", VALUES)
def test_integer_storage_strict_values(library, value):
    integer = fresh_integer(value)
    if abs(value) >= 2**53:
        with pytest.raises(TypeError, match="Integer exceeds 53-bit range"):
            library.dumps([integer], option=library.OPT_STRICT_INTEGER)
    else:
        assert library.dumps([integer], option=library.OPT_STRICT_INTEGER) == reference_bytes([value])
    assert library.dumps([-1, 0, 2**64 - 1]) == b"[-1,0,18446744073709551615]"


@pytest.mark.parametrize("value", VALUES)
def test_integer_storage_converted_keys_ignore_strict_limit(library, value):
    option = library.OPT_NON_STR_KEYS | library.OPT_STRICT_INTEGER
    assert library.dumps({fresh_integer(value): -1}, option=option) == (
        b'{"' + str(value).encode() + b'":-1}'
    )


@pytest.mark.parametrize("value", [-(2**63), 2**63, 2**64 - 1])
def test_integer_storage_keys_restore_strict_values(library, value):
    values = {fresh_integer(value): 0, "invalid": 2**53}
    option = library.OPT_NON_STR_KEYS | library.OPT_STRICT_INTEGER
    with pytest.raises(TypeError, match="Integer exceeds 53-bit range"):
        library.dumps(values, option=option)
    assert library.dumps([fresh_integer(value), -1]) == reference_bytes([value, -1])


def test_integer_storage_preserves_converted_key_duplicates(library):
    values = {"1": 0, 1: 1, "-1": 2, -1: 3}
    assert library.dumps(values, option=library.OPT_NON_STR_KEYS) == b'{"1":0,"1":1,"-1":2,"-1":3}'


@pytest.mark.parametrize("value", [-(2**63) - 1, 2**64, -(2**64), 2**65, -(2**89), 2**90, -(2**4096), 2**4096])
@pytest.mark.parametrize("strict", [False, True])
def test_integer_storage_overflow_precedes_strict(value, strict):
    option = jsonmodem.OPT_STRICT_INTEGER if strict else 0
    integer = fresh_integer(value)
    for container in (integer, [0, integer], {"value": integer}):
        with pytest.raises(TypeError, match="Integer exceeds 64-bit range"):
            jsonmodem.dumps(container, option=option)
    with pytest.raises(TypeError, match="Integer exceeds 64-bit range"):
        jsonmodem.dumps({integer: 0}, option=option | jsonmodem.OPT_NON_STR_KEYS)
    assert jsonmodem.dumps([0, -1, 2**64 - 1]) == b"[0,-1,18446744073709551615]"


@pytest.mark.parametrize("value", WIDE_VALUES)
def test_integer_storage_first_and_repeated_use(library, value):
    prefix = [None, True, False, "text", 1.5, [], (), {"empty": []}]
    first = fresh_integer(value)
    distinct = fresh_integer(value, "decimal")
    for values in (prefix + [first], [first] + prefix + [first, distinct]):
        assert library.dumps(values) == reference_bytes(values)


def test_integer_storage_noninteger_controls(library):
    values = [None, True, False, "text", 1.5, [], (), {"value": "string"}]
    assert library.dumps(values) == reference_bytes(values)
    assert library.dumps(True) == b"true"
    assert library.dumps(False) == b"false"


def test_integer_storage_random_values(library):
    rng = random.Random(3791)
    values = [fresh_integer(rng.randrange(-(2**63), 2**64)) for _ in range(257)]
    assert library.dumps(values) == reference_bytes(values)
    assert library.dumps(tuple(reversed(values))) == reference_bytes(tuple(reversed(values)))


@pytest.mark.parametrize("value", WIDE_VALUES)
def test_integer_storage_subclasses_keep_base_value(library, value):
    class IntegerSubclass(int):
        def __int__(self):
            raise AssertionError("__int__ must not run")

        def __index__(self):
            raise AssertionError("__index__ must not run")

        def __str__(self):
            raise AssertionError("__str__ must not run")

        def __repr__(self):
            raise AssertionError("__repr__ must not run")

    integer = IntegerSubclass(value)
    assert library.dumps([integer]) == reference_bytes([value])
    assert library.dumps({integer: 0}, option=library.OPT_NON_STR_KEYS) == reference_bytes({str(value): 0})
    calls = []

    def default(obj):
        assert obj is integer
        calls.append(obj)
        return fresh_integer(value)

    assert library.dumps(
        integer, default=default, option=library.OPT_PASSTHROUGH_SUBCLASS
    ) == str(value).encode()
    assert calls == [integer]


@pytest.mark.parametrize("value", WIDE_VALUES)
def test_integer_storage_enum_and_dataclass(library, value):
    enum_type = IntEnum("IntegerEnum", {"VALUE": value})

    @dataclass
    class Row:
        value: int

    assert library.dumps([enum_type.VALUE, Row(fresh_integer(value))]) == reference_bytes(
        [value, {"value": value}]
    )


@pytest.mark.parametrize("value", WIDE_VALUES)
def test_integer_storage_callback_return_and_reentry(library, value):
    marker = object()
    calls = []

    def default(obj):
        assert obj is marker
        calls.append(obj)
        gc.collect()
        assert library.dumps([fresh_integer(value), -1]) == reference_bytes([value, -1])
        return fresh_integer(value)

    assert library.dumps([2**60, marker, -1], default=default) == reference_bytes([2**60, value, -1])
    assert calls == [marker]


@pytest.mark.parametrize("value", [-(2**63), 2**63, 2**64 - 1])
def test_integer_storage_callback_mutation_keeps_owners(value):
    marker = object()
    values = [fresh_integer(value), marker, fresh_integer(value, "decimal")]

    def default(obj):
        assert obj is marker
        values.clear()
        gc.collect()
        assert jsonmodem.dumps([fresh_integer(value)]) == reference_bytes([value])
        return -1

    assert jsonmodem.dumps(values, default=default) == reference_bytes([value, -1, value])
    assert values == []


def test_integer_storage_callback_failure_and_later_success():
    marker = object()

    def default(obj):
        assert obj is marker
        raise ValueError("callback failure")

    with pytest.raises(TypeError):
        jsonmodem.dumps([2**64 - 1, marker], default=default)
    assert jsonmodem.dumps([-1, 2**63, 2**64 - 1]) == b"[-1,9223372036854775808,18446744073709551615]"


def test_integer_storage_does_not_convert_unrelated_index_object():
    class IndexOnly:
        def __index__(self):
            raise AssertionError("__index__ must not run")

    value = IndexOnly()
    calls = []

    def default(obj):
        assert obj is value
        calls.append(obj)
        return 2**64 - 1

    assert jsonmodem.dumps([0, value], default=default) == b"[0,18446744073709551615]"
    assert calls == [value]
