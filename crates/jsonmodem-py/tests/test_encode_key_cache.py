"""Preserve key bytes and ownership when cache lookups are skipped."""

import dataclasses
import json
import sys

import pytest

import jsonmodem


def expected_bytes(value, option=0):
    kwargs = {
        "ensure_ascii": False,
        "sort_keys": bool(option & jsonmodem.OPT_SORT_KEYS),
    }
    if option & jsonmodem.OPT_INDENT_2:
        kwargs["indent"] = 2
    else:
        kwargs["separators"] = (",", ":")
    output = json.dumps(value, **kwargs).encode()
    if option & jsonmodem.OPT_APPEND_NEWLINE:
        output += b"\n"
    return output


@pytest.mark.parametrize("prefix_length", [0, 1018, 1019, 1020, 1024, 2048])
@pytest.mark.parametrize(
    "key",
    ["", "key", "x" * 64, "x" * 65, "\u00e9" * 32, "\u00e9" * 33, "\n\"\\\x00"],
)
@pytest.mark.parametrize("option", [0, jsonmodem.OPT_INDENT_2])
def test_keys_across_cache_activation(prefix_length, key, option):
    # In compact output, the first key starts after prefix_length + 5 bytes.
    value = ["x" * prefix_length, {key: 0}]
    value.extend({key: index} for index in range(32))
    assert jsonmodem.dumps(value, option=option) == expected_bytes(value, option)


@pytest.mark.parametrize("position", range(16))
@pytest.mark.parametrize(
    "option",
    [0, jsonmodem.OPT_INDENT_2, jsonmodem.OPT_SORT_KEYS, jsonmodem.OPT_APPEND_NEWLINE],
)
def test_every_retained_key_after_full_cache(position, option):
    keys = [f"retained_key_{index:02d}\n\"\u00e9" for index in range(16)]
    value = ["x" * 2048, dict.fromkeys(keys, None)]
    for index in range(64):
        value.extend([{f"new_key_{index}": index}, {keys[position]: index}])
    assert jsonmodem.dumps(value, option=option) == expected_bytes(value, option)


def colliding_keys(count):
    """Keep candidate strings alive while finding one shared filter bit."""
    buckets = [[] for _ in range(64)]
    for index in range(64 * (count - 1) + 1):
        key = f"collision_key_{index}\n\""
        identity = id(key)
        bucket = ((identity >> 4) ^ (identity >> 10)) & 63
        buckets[bucket].append(key)
        if len(buckets[bucket]) == count:
            return buckets[bucket]
    raise AssertionError("one of 64 buckets must contain the requested count")


@pytest.mark.parametrize("count", [1, 2, 15, 16, 17, 64, 65])
def test_filter_collisions_still_compare_full_identity(count):
    keys = colliding_keys(count)
    records = [{key: index} for index, key in enumerate(keys)]
    value = ["x" * 2048, records * 8, list(reversed(records))]
    assert jsonmodem.dumps(value) == expected_bytes(value)


@pytest.mark.parametrize("count", [15, 16, 17, 128])
def test_cached_ranges_survive_output_growth(count):
    keys = [f"escaped\n\"\u00e9_{index}" for index in range(count)]
    value = ["x" * 2048, dict.fromkeys(keys, 0)]
    for size in (256, 4096, 65536):
        value.extend(["\u00e9\\" * size, dict.fromkeys(keys, size)])
    assert jsonmodem.dumps(value) == expected_bytes(value)


def test_equal_text_in_distinct_owners():
    seed = "a repeated escaped key\n\"\u00e9"
    keys = [seed.encode().decode() for _ in range(64)]
    assert len({id(key) for key in keys}) == len(keys)
    value = ["x" * 2048, [{key: index} for index, key in enumerate(keys)] * 4]
    assert jsonmodem.dumps(value) == expected_bytes(value)


@pytest.mark.parametrize("count", [15, 16, 17, 80])
def test_late_callback_restart_rebuilds_key_ranges(count):
    class Wrapped:
        pass

    keys = [f"retained\n\"key_{index}" for index in range(count)]
    value = ["x" * 2048, [dict.fromkeys(keys, index) for index in range(40)], Wrapped()]
    calls = []

    def default(value):
        calls.append(type(value))
        return dict.fromkeys(keys, "callback")

    expected = [*value[:-1], dict.fromkeys(keys, "callback")]
    assert jsonmodem.dumps(value, default=default) == expected_bytes(expected)
    assert calls == [Wrapped]


def test_callback_uses_retained_entries_after_source_is_cleared():
    first = object()
    last = object()
    source = {f"key_{index:02d}": index for index in range(32)}
    source["first_callback"] = first
    source["last_callback"] = last
    expected = ["x" * 2048, {**source, "first_callback": 1, "last_callback": 2}]
    calls = []

    def default(value):
        calls.append(value)
        source.clear()
        return 1 if value is first else 2

    assert jsonmodem.dumps(["x" * 2048, source], default=default) == expected_bytes(expected)
    assert calls == [first, last]


@pytest.mark.skipif(
    sys.implementation.name != "cpython" or bool(getattr(sys, "_is_gil_enabled", lambda: True)()) is False,
    reason="checks GIL-enabled CPython reference counts",
)
def test_checked_cache_retains_first_sixteen_field_owners():
    @dataclasses.dataclass
    class Record:
        pass

    record = Record()
    names = [f"field_{index}" for index in range(17)]
    # Avoid references retained by CPython's shared instance-key table.
    record.__dict__ = dict(zip(names, range(17)))
    value = ["x" * 2048, record, object()]
    expected = [value[0], dict(zip(names, range(17))), None]
    references = [sys.getrefcount(name) for name in names]
    calls = []

    def default(item):
        calls.append(item)
        record.__dict__.clear()
        assert [sys.getrefcount(name) for name in names] == [
            count - int(index == 16) for index, count in enumerate(references)
        ]
        return None

    assert jsonmodem.dumps(value, default=default) == expected_bytes(expected)
    assert calls == [value[2]]
    assert [sys.getrefcount(name) for name in names] == [count - 1 for count in references]


@pytest.mark.parametrize("key", ["\ud800", "\udfff", "key\ud800"])
def test_invalid_key_after_cache_is_full(key):
    value = ["x" * 2048, {f"key_{index}": index for index in range(16)}, {key: 1}]
    with pytest.raises(TypeError, match="UTF-8"):
        jsonmodem.dumps(value)


def test_duplicate_converted_keys_after_cache_is_full():
    prefix = ["x" * 2048, {f"key_{index}": index for index in range(16)}]
    value = [*prefix, {"1": "text", 1: "number", "null": "text", None: "none"}]
    expected = (
        expected_bytes(prefix)[:-1]
        + b',{"1":"text","1":"number","null":"text","null":"none"}]'
    )
    assert jsonmodem.dumps(value, option=jsonmodem.OPT_NON_STR_KEYS) == expected
