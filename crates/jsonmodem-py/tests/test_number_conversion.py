"""Integer boundaries exercise native conversion without optional dependencies."""

import json
import random

import pytest

import jsonmodem


def integer_values():
    rng = random.Random(2901)
    values = [-(2**63), -1, 0, 1, 2**63 - 1, 2**63, 2**64 - 1]
    for bits in range(65):
        for delta in (-1, 0, 1):
            for sign in (-1, 1):
                value = sign * (2**bits + delta)
                if -(2**63) <= value < 2**64:
                    values.append(value)
    values.extend(rng.randrange(-(2**63), 2**64) for _ in range(5000))
    rng.shuffle(values)
    return values


@pytest.mark.parametrize("option", [0, jsonmodem.OPT_INDENT_2, jsonmodem.OPT_APPEND_NEWLINE])
def test_signed_and_unsigned_integer_output(option):
    values = integer_values()
    kwargs = {"indent": 2} if option & jsonmodem.OPT_INDENT_2 else {"separators": (",", ":")}
    expected = json.dumps(values, **kwargs).encode()
    if option & jsonmodem.OPT_APPEND_NEWLINE:
        expected += b"\n"
    assert jsonmodem.dumps(values, option=option) == expected
    assert jsonmodem.dumps(tuple(values), option=option) == expected


@pytest.mark.parametrize("value", [-(2**63) - 1, 2**64, -(2**128), 2**128, -(2**4096), 2**4096])
def test_integer_range_errors_leave_no_python_exception(value):
    for _ in range(3):
        with pytest.raises(TypeError, match="Integer exceeds 64-bit range"):
            jsonmodem.dumps([0, value, 1])
        assert jsonmodem.dumps([-1, 0, 2**63, 2**64 - 1]) == (
            b"[-1,0,9223372036854775808,18446744073709551615]"
        )


def test_unsigned_integers_and_minus_one_leave_no_python_exception():
    values = [-1, 2**63, -1, 2**64 - 1] * 1000
    assert jsonmodem.dumps(values) == json.dumps(values, separators=(",", ":")).encode()
    assert jsonmodem.dumps(-1) == b"-1"
    assert jsonmodem.loads(b"[-1,0,1]") == [-1, 0, 1]


def test_strict_integer_applies_to_values_but_not_integer_keys():
    option = jsonmodem.OPT_NON_STR_KEYS | jsonmodem.OPT_STRICT_INTEGER
    keys = [-(2**63), -(2**53), -1, 2**53, 2**63, 2**64 - 1]
    value = {key: -1 for key in keys}
    expected = json.dumps({str(key): -1 for key in keys}, separators=(",", ":")).encode()
    assert jsonmodem.dumps(value, option=option) == expected
    for value in (-(2**63), -(2**53), 2**53, 2**63, 2**64 - 1):
        with pytest.raises(TypeError, match="Integer exceeds 53-bit range"):
            jsonmodem.dumps({2**64 - 1: value}, option=option)
        assert jsonmodem.dumps({2**64 - 1: -1}, option=option) == (
            b'{"18446744073709551615":-1}'
        )


def test_integer_subclass_conversions_do_not_run_overrides():
    class Integer(int):
        def __index__(self):
            raise AssertionError("must use the stored integer")

        def __int__(self):
            raise AssertionError("must use the stored integer")

    values = [Integer(value) for value in (-(2**63), -1, 0, 2**63, 2**64 - 1)]
    assert jsonmodem.dumps(values) == b"[-9223372036854775808,-1,0,9223372036854775808,18446744073709551615]"


@pytest.mark.parametrize("value", [-(2**63), -1, 0, 2**63, 2**64 - 1])
def test_integer_from_default(value):
    assert jsonmodem.dumps([object()], default=lambda _: value) == (
        b"[" + str(value).encode() + b"]"
    )
