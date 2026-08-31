"""Preserve dictionary output and owners across scalar and owned entries."""

import gc
import json

import pytest

import jsonmodem


def integer(value):
    return int(str(value))


CASES = [
    ("none", lambda: None, None),
    ("true", lambda: True, True),
    ("false", lambda: False, False),
    ("zero", lambda: integer(0), 0),
    ("negative_one", lambda: integer(-1), -1),
    ("fresh_positive", lambda: integer(257), 257),
    ("fresh_negative", lambda: integer(-257), -257),
    ("compact_max", lambda: integer(2**30 - 1), 2**30 - 1),
    ("compact_min", lambda: integer(-(2**30) + 1), -(2**30) + 1),
    ("multidigit_positive", lambda: integer(2**30), 2**30),
    ("multidigit_negative", lambda: integer(-(2**30)), -(2**30)),
    ("signed_max", lambda: integer(2**63 - 1), 2**63 - 1),
    ("signed_min", lambda: integer(-(2**63)), -(2**63)),
    ("unsigned_max", lambda: integer(2**64 - 1), 2**64 - 1),
    ("float_zero", lambda: 0.0, 0.0),
    ("negative_zero", lambda: -0.0, -0.0),
    ("float", lambda: 1.5, 1.5),
    ("infinity", lambda: float("inf"), None),
    ("negative_infinity", lambda: float("-inf"), None),
    ("nan", lambda: float("nan"), None),
    ("empty_string", lambda: "", ""),
    ("ascii", lambda: "".join(("fresh", " text")), "fresh text"),
    ("escaped", lambda: "".join(("a", '\0\n\r\t\b\f"\\z')), 'a\0\n\r\t\b\f"\\z'),
    ("unicode", lambda: "".join(("\u00e9", "\U0001f600")), "\u00e9\U0001f600"),
    ("empty_dict", dict, {}),
    ("empty_list", list, []),
    ("empty_tuple", tuple, []),
    ("dict", lambda: {"inner": 257}, {"inner": 257}),
    ("list", lambda: [257, "x"], [257, "x"]),
    ("tuple", lambda: (257, "x"), [257, "x"]),
]
OPTIONS = [
    0,
    jsonmodem.OPT_INDENT_2,
    jsonmodem.OPT_APPEND_NEWLINE,
    jsonmodem.OPT_INDENT_2 | jsonmodem.OPT_APPEND_NEWLINE,
    jsonmodem.OPT_SORT_KEYS,
    jsonmodem.OPT_NON_STR_KEYS,
]


def expected_json(value, option):
    if option & jsonmodem.OPT_INDENT_2:
        text = json.dumps(value, ensure_ascii=False, indent=2,
                          sort_keys=bool(option & jsonmodem.OPT_SORT_KEYS))
    else:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                          sort_keys=bool(option & jsonmodem.OPT_SORT_KEYS))
    return text.encode() + (b"\n" if option & jsonmodem.OPT_APPEND_NEWLINE else b"")


@pytest.mark.parametrize("name, make, expected", CASES, ids=[case[0] for case in CASES])
@pytest.mark.parametrize("option", OPTIONS)
@pytest.mark.parametrize("padding", [0, 1020, 2048])
def test_mixed_dictionary_entries(name, make, expected, option, padding):
    value = {"padding": "x" * padding, "before": 257, "value": make(), "after": -257}
    normalized = {"padding": "x" * padding, "before": 257, "value": expected, "after": -257}
    assert jsonmodem.dumps(value, option=option) == expected_json(normalized, option)


@pytest.mark.parametrize("value", [-(2**53), -(2**30), -257, -1, 0, 257, 2**30, 2**53 - 1, 2**53, 2**64 - 1])
def test_strict_integer_fallback(value):
    record = {"before": 257, "value": integer(value), "after": -1}
    if abs(value) >= 2**53:
        with pytest.raises(TypeError, match="Integer exceeds 53-bit range"):
            jsonmodem.dumps(record, option=jsonmodem.OPT_STRICT_INTEGER)
    else:
        assert jsonmodem.dumps(record, option=jsonmodem.OPT_STRICT_INTEGER) == expected_json(record, 0)
    assert jsonmodem.dumps({"value": -1}) == b'{"value":-1}'


@pytest.mark.parametrize("value", [-(2**63) - 1, 2**64, -(2**128), 2**128])
def test_integer_error_after_accepted_entries(value):
    with pytest.raises(TypeError, match="Integer exceeds 64-bit range"):
        jsonmodem.dumps({"padding": "x" * 2048, "before": 257, "value": integer(value)})
    assert jsonmodem.dumps({"value": 2**64 - 1}) == b'{"value":18446744073709551615}'


@pytest.mark.parametrize("key", ["\u00e9", "\U0001f600", "cold_\u00e9_\U0001f600"])
@pytest.mark.parametrize("option", OPTIONS)
def test_non_ascii_keys_keep_owned_output(key, option):
    key = "".join((key, "_suffix"))
    record = {"padding": "x" * 2048, key: 257, "after": "ascii"}
    assert jsonmodem.dumps(record, option=option) == expected_json(record, option)


@pytest.mark.parametrize("count", [1, 15, 16, 17, 64])
@pytest.mark.parametrize("length", [0, 1, 63, 64, 65])
def test_repeated_keys_and_output_growth(count, length):
    keys = [("x" * length + str(index) + '\n"').encode().decode() for index in range(count)]
    rows = [dict.fromkeys(keys, index) for index in range(40)]
    value = ["x" * 2048, rows]
    assert jsonmodem.dumps(value) == expected_json(value, 0)


@pytest.mark.parametrize("padding", [1006, 1007, 1008, 1023, 1024, 1025])
def test_cache_activation_after_scalar_prefix(padding):
    keys = [f"field_{index:03d}" for index in range(20)]
    record = {"padding": "x" * padding}
    record.update(dict.fromkeys(keys, 257))
    value = [record, dict.fromkeys(keys, -257)]
    assert jsonmodem.dumps(value) == expected_json(value, 0)


def test_deleted_slots_and_shared_containers():
    record = {f"field_{index}": index for index in range(100)}
    for index in range(0, 100, 3):
        del record[f"field_{index}"]
    for index in range(20):
        record[f"added_{index}"] = "text"
    value = [record, {"child": record}, record]
    assert jsonmodem.dumps(value) == expected_json(value, 0)


def test_converted_keys_keep_duplicate_names_and_strict_exception():
    value = {"before": 257, 1: 2, "1": 3, 2**63: 4, "after": -1}
    option = jsonmodem.OPT_NON_STR_KEYS | jsonmodem.OPT_STRICT_INTEGER
    assert jsonmodem.dumps(value, option=option) == (
        b'{"before":257,"1":2,"1":3,"9223372036854775808":4,"after":-1}'
    )


@pytest.mark.parametrize("base, value, expected", [(str, "text", "text"), (int, 257, 257)])
def test_subclass_conversion_overrides_are_not_called(base, value, expected):
    class Child(base):
        def __str__(self):
            raise AssertionError("__str__")

        def __repr__(self):
            raise AssertionError("__repr__")

        def __int__(self):
            raise AssertionError("__int__")

        def __index__(self):
            raise AssertionError("__index__")

        def __float__(self):
            raise AssertionError("__float__")

    assert jsonmodem.dumps({"before": 257, "value": Child(value), "after": -1}) == (
        expected_json({"before": 257, "value": expected, "after": -1}, 0)
    )


def test_float_subclass_is_rejected_without_conversion():
    calls = []

    class Child(float):
        def __str__(self):
            calls.append("__str__")
            raise AssertionError("__str__")

        def __repr__(self):
            calls.append("__repr__")
            raise AssertionError("__repr__")

        def __float__(self):
            calls.append("__float__")
            raise AssertionError("__float__")

    with pytest.raises(TypeError, match="Type is not JSON serializable: Child"):
        jsonmodem.dumps({"before": 257, "value": Child(1.5), "after": -1})
    assert calls == []


def test_string_subclass_key_keeps_fallback():
    class Key(str):
        def __str__(self):
            raise AssertionError("__str__")

    value = {"before": 257, Key("key"): 1, "after": -1}
    with pytest.raises(TypeError, match="Dict key must be str"):
        jsonmodem.dumps(value)
    assert jsonmodem.dumps(value, option=jsonmodem.OPT_NON_STR_KEYS) == (
        b'{"before":257,"key":1,"after":-1}'
    )


def test_fragment_stays_on_owned_scalar_handling():
    value = {"before": 257, "value": jsonmodem.Fragment(b'{"raw":1}'), "after": -1}
    assert jsonmodem.dumps(value) == b'{"before":257,"value":{"raw":1},"after":-1}'


@pytest.mark.parametrize("depth", [1, 32, 253, 254, 255])
def test_nested_dictionaries_keep_depth_limit(depth):
    value = 0
    for _ in range(depth):
        value = {"value": value}
    if depth > 254:
        with pytest.raises(TypeError, match="Recursion limit reached"):
            jsonmodem.dumps(value)
    else:
        assert jsonmodem.dumps(value) == b'{"value":' * depth + b"0" + b"}" * depth


def test_dictionary_cycle_is_not_accepted_as_scalar():
    value = {"before": 257}
    value["cycle"] = value
    with pytest.raises(TypeError, match="circular reference"):
        jsonmodem.dumps(value)


def test_default_mutation_and_reentry_keep_owned_entries():
    marker = object()
    value = {"padding": "x" * 2048, "before": 257, "value": marker, "after": [-257, "ascii"]}
    expected = {"padding": "x" * 2048, "before": 257, "value": 0, "after": [-257, "ascii"]}
    calls = []

    def default(obj):
        assert obj is marker
        calls.append(obj)
        value.clear()
        gc.collect()
        assert jsonmodem.dumps({"nested": 257}) == b'{"nested":257}'
        return 0

    assert jsonmodem.dumps(value, default=default) == expected_json(expected, 0)
    assert not value and calls == [marker]


@pytest.mark.parametrize("key, message", [("\ud800", "str is not valid UTF-8"), (object(), "Dict key must be str")])
def test_key_errors_precede_value_overflow(key, message):
    value = {"before": 257, key: 2**128}
    with pytest.raises(TypeError, match=message):
        jsonmodem.dumps(value)
