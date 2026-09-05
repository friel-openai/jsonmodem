"""Numeric prefixes retain values, errors and callback ordering."""

import json
import math

import pytest

import jsonmodem
import jsonmodem.portable as portable


@pytest.mark.parametrize("count", [0, 1, 2, 15, 16, 17, 127, 128, 129, 1024])
@pytest.mark.parametrize("suffix", [None, False, "tail", [], [1], {}, {"x": 1}])
@pytest.mark.parametrize("option", [0, jsonmodem.OPT_APPEND_NEWLINE, jsonmodem.OPT_INDENT_2])
def test_numeric_prefix_keeps_the_first_other_value(count, suffix, option):
    values = list(range(count)) + [suffix, 7, 0.25, "last"]
    result = jsonmodem.dumps(values, option=option)
    assert result == portable.dumps(values, option=option)
    assert json.loads(result) == values


@pytest.mark.parametrize("count", [1, 16, 129])
def test_numeric_runs_preserve_float_spelling(count):
    values = [1, -0.0, math.inf, -math.inf, math.nan, 0.25] * count
    result = jsonmodem.dumps(values)
    assert result == portable.dumps(values)
    assert result == b"[" + b",".join([b"1,-0.0,null,null,null,0.25"] * count) + b"]"


@pytest.mark.parametrize("bad", [-(1 << 63) - 1, 1 << 64])
@pytest.mark.parametrize("prefix", [[], [0], list(range(129))])
def test_integer_range_error_does_not_reach_later_callback(bad, prefix):
    for dumps in (jsonmodem.dumps, portable.dumps):
        calls = []
        with pytest.raises(TypeError, match="Integer exceeds 64-bit range"):
            dumps(prefix + [bad, object()], default=lambda value: calls.append(value))
        assert calls == []


@pytest.mark.parametrize("bad", [-(1 << 53), 1 << 53])
def test_strict_integer_error_keeps_callback_priority(bad):
    for dumps in (jsonmodem.dumps, portable.dumps):
        calls = []
        with pytest.raises(TypeError, match="Integer exceeds 53-bit range"):
            dumps([1, bad, object()], default=lambda value: calls.append(value),
                  option=jsonmodem.OPT_STRICT_INTEGER)
        assert calls == []
        marker = object()
        with pytest.raises(TypeError, match="Integer exceeds 53-bit range"):
            dumps([1, marker, bad], default=lambda value: calls.append(value),
                  option=jsonmodem.OPT_STRICT_INTEGER)
        assert calls == [marker]


def test_late_callback_mutation_and_recursive_call_match_portable():
    def run(dumps):
        marker = object()
        values = list(range(129)) + [marker, 100]
        calls = []

        def default(value):
            assert value is marker
            calls.append(value)
            values[-1] = 200
            return json.loads(dumps([17, 0.25]))

        result = dumps(values, default=default)
        assert calls == [marker]
        return result

    assert run(jsonmodem.dumps) == run(portable.dumps)


def test_integer_subclass_still_uses_supported_behavior():
    class CustomInt(int):
        pass

    values = [1, 2, CustomInt(3), 4]
    assert jsonmodem.dumps(values) == portable.dumps(values) == b"[1,2,3,4]"


def test_nested_numeric_runs_preserve_tuple_and_list_order():
    values = [list(range(16)), tuple(range(16)), [1, [2, 3], 4], [True, 0, False]]
    assert jsonmodem.dumps(values) == portable.dumps(values)
    assert json.loads(jsonmodem.dumps(values)) == [
        list(range(16)), list(range(16)), [1, [2, 3], 4], [True, 0, False]
    ]
