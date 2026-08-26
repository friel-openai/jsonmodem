"""Sorted dictionary output while temporary key/value storage is reused."""

import json
import random

import pytest

import jsonmodem


@pytest.mark.parametrize("count", [0, 1, 4, 8, 16, 64, 65, 1000])
@pytest.mark.parametrize("order", ["ascending", "descending", "shuffled"])
@pytest.mark.parametrize("extra", [0, jsonmodem.OPT_INDENT_2, jsonmodem.OPT_APPEND_NEWLINE])
def test_sorted_dictionary_sizes_and_nested_values(count, order, extra):
    indices = list(range(count))
    if order == "descending":
        indices.reverse()
    elif order == "shuffled":
        random.Random(6843).shuffle(indices)
    mapping = {f"key-{index:04d}": index for index in indices}
    value = [mapping, {"nested": dict(mapping)}, {}, dict(mapping), {"\u2603": 1, "\u00e9": 2}]
    kwargs = {"indent": 2} if extra & jsonmodem.OPT_INDENT_2 else {"separators": (",", ":")}
    expected = json.dumps(value, sort_keys=True, ensure_ascii=False, **kwargs).encode()
    if extra & jsonmodem.OPT_APPEND_NEWLINE:
        expected += b"\n"
    assert jsonmodem.dumps(value, option=jsonmodem.OPT_SORT_KEYS | extra) == expected


def test_large_sorted_dictionary_between_small_dictionaries():
    small = {"z": 3, "a": 1, "m": 2}
    large = {f"key-{index:05d}": index for index in reversed(range(10000))}
    value = [small, large, small, {"next": small}, small]
    expected = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    assert jsonmodem.dumps(value, option=jsonmodem.OPT_SORT_KEYS) == expected


def test_sorted_nested_parents_after_larger_children():
    preload = {f"{index:02x}": 0 for index in range(64)}
    value = 0
    for _ in range(128):
        value = {"a": preload, "b": value}
    expected = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    assert jsonmodem.dumps(value, option=jsonmodem.OPT_SORT_KEYS) == expected


@pytest.mark.parametrize("extra", [0, jsonmodem.OPT_INDENT_2])
def test_sorted_prefix_before_converted_key_collisions(extra):
    prefix = [{"z": index, "a": index + 1} for index in range(20)]
    value = prefix + [{2: "integer", "2": "text"}, {"b": 3, "a": 4}]
    encoded = jsonmodem.dumps(
        value, option=jsonmodem.OPT_SORT_KEYS | jsonmodem.OPT_NON_STR_KEYS | extra
    )
    pairs = json.loads(encoded, object_pairs_hook=list)
    assert pairs[:-2] == [[("a", index + 1), ("z", index)] for index in range(20)]
    assert pairs[-2] == [("2", "integer"), ("2", "text")]
    assert pairs[-1] == [("a", 4), ("b", 3)]


def test_sorted_string_subclass_keys_do_not_call_overrides():
    class Key(str):
        def __lt__(self, other):
            raise AssertionError("comparison must use the stored string")

        def __str__(self):
            raise AssertionError("conversion must use the stored string")

    value = [{"z": 3, "a": 1}, {Key("b"): 2, Key("a"): 1}, {"c": 3}]
    assert jsonmodem.dumps(value, option=jsonmodem.OPT_SORT_KEYS) == (
        b'[{"a":1,"z":3},{"a":1,"b":2},{"c":3}]'
    )


def test_sorted_storage_is_released_after_errors():
    prefix = {"z": 2, "a": 1}
    with pytest.raises(TypeError, match="str is not valid UTF-8"):
        jsonmodem.dumps([prefix, {"ok": 1, "\ud800": 2}], option=jsonmodem.OPT_SORT_KEYS)
    cyclic = {"first": prefix}
    cyclic["self"] = cyclic
    with pytest.raises(TypeError, match="circular reference"):
        jsonmodem.dumps(cyclic, option=jsonmodem.OPT_SORT_KEYS)
    assert jsonmodem.dumps(prefix, option=jsonmodem.OPT_SORT_KEYS) == b'{"a":1,"z":2}'
