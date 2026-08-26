"""Exact integer and floating-point conversion checks."""

import json
import math
import random
import struct

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


def test_signed_and_unsigned_integer_input():
    values = integer_values()
    actual = jsonmodem.loads(json.dumps(values))
    assert actual == values
    assert all(type(value) is int for value in actual)


def test_integer_input_overflow_uses_finite_double_conversion():
    rng = random.Random(3581)
    values = [-(2**63) - 1, 2**64, -(2**64), 2**64 + 1]
    values.extend((-1 if rng.getrandbits(1) else 1) * rng.getrandbits(bits)
                  for bits in range(65, 1100))
    for value in values:
        text = str(value)
        expected = value if -(2**63) <= value < 2**64 else float(text)
        if not math.isfinite(expected):
            with pytest.raises(jsonmodem.JSONDecodeError, match="infinity"):
                jsonmodem.loads(text)
        else:
            actual = jsonmodem.loads(text)
            assert type(actual) is type(expected)
            assert actual == expected


@pytest.mark.parametrize("text", ["0", "-0", "0.0", "-0.0", "0e0", "-0e0", "0.0e-999", "-0.0e-999"])
def test_numeric_zero_type_and_sign(text):
    expected = float(text) if any(char in text for char in ".eE") else int(text)
    actual = jsonmodem.loads(text)
    assert type(actual) is type(expected)
    assert actual == expected
    assert math.copysign(1.0, actual) == math.copysign(1.0, expected)


@pytest.mark.parametrize("text,offset", [
    ("-", 1), ("1.", 2), ("1.e2", 2), ("1e", 2), ("1e+", 3), ("1e-", 3),
    ("18446744073709551616.", 21), ("18446744073709551616e-", 22),
])
def test_invalid_numeric_offsets(text, offset):
    prefix = '["\u00e9",'
    with pytest.raises(jsonmodem.JSONDecodeError) as caught:
        jsonmodem.loads(prefix + text + "]")
    assert caught.value.pos == len(prefix) + offset


@pytest.mark.parametrize("text", ["+1", ".1", "--1", "01", "-01", "1_000", "0x10", "1..0", "1e++2", "1.0e-+2"])
def test_invalid_numeric_grammar(text):
    with pytest.raises(jsonmodem.JSONDecodeError):
        jsonmodem.loads(text)
    with pytest.raises(jsonmodem.JSONDecodeError):
        jsonmodem.loads("[" + text + "]")


def test_float_input_bits_match_orjson():
    orjson = pytest.importorskip("orjson")
    rng = random.Random(9251)
    values = [struct.unpack("<d", rng.getrandbits(64).to_bytes(8, "little"))[0] for _ in range(10000)]
    values = [value for value in values if math.isfinite(value)]
    document = orjson.dumps(values)
    actual = jsonmodem.loads(document)
    expected = orjson.loads(document)
    assert [struct.pack("<d", value) for value in actual] == [struct.pack("<d", value) for value in expected]


@pytest.mark.parametrize("text", [
    "1.7976931348623157e308", "1.7976931348623158e308", "-1.7976931348623157e308",
    "2.2250738585072014e-308", "2.2250738585072011e-308", "5e-324", "-5e-324",
    "2.4703282292062327e-324", "2.4703282292062328e-324", "-1e-999", "1e-999",
    "9007199254740993.0", "18446744073709551615.0", "18446744073709551616e0",
    "1.00000000000000011102230246251565404236316680908203125",
    "1.00000000000000011102230246251565404236316680908203126",
    "1.00000000000000033306690738754696212708950042724609375",
    "-1.00000000000000011102230246251565404236316680908203125",
])
def test_float_rounding_boundaries(text):
    expected = struct.pack("<d", float(text))
    for document in (text, text + " \r\n\t", "[" + text + "]", '{"value":' + text + "}"):
        actual = jsonmodem.loads(document)
        if isinstance(actual, list):
            actual = actual[0]
        elif isinstance(actual, dict):
            actual = actual["value"]
        assert type(actual) is float
        assert struct.pack("<d", actual) == expected


@pytest.mark.parametrize("text", [
    "1.7976931348623159e308", "-1.7976931348623159e308", "1e400", "-1e400",
    "1e9999999999999999999999999999999", "-1e9999999999999999999999999999999",
])
def test_float_overflow_is_not_materialized(text):
    for document in (text, "[" + text + "]", '{"value":' + text + "}"):
        with pytest.raises(jsonmodem.JSONDecodeError, match="infinity"):
            jsonmodem.loads(document)


@pytest.mark.parametrize("zero_count", [64, 512, 1200])
def test_float_long_mantissas_and_exponents(zero_count):
    zeros = "0" * zero_count
    midpoint = "1.00000000000000011102230246251565404236316680908203125"
    values = [
        f"0.{zeros}1e{zero_count}", f"1{zeros}e-{zero_count}",
        f"-0.{zeros}1", f"1e{zeros}1", f"1e-{zeros}1",
        midpoint + zeros, midpoint + zeros + "1", "-" + midpoint + zeros + "1",
    ]
    actual = jsonmodem.loads("[" + ",".join(values) + "]")
    expected = [float(text) for text in values]
    assert [struct.pack("<d", value) for value in actual] == [struct.pack("<d", value) for value in expected]


def test_random_decimal_float_rounding():
    rng = random.Random(69251)
    texts = []
    for _ in range(10000):
        digits = str(rng.randrange(1, 10**rng.randrange(1, 100)))
        fraction = rng.randrange(len(digits) + 1)
        if fraction:
            digits = (digits[:-fraction] or "0") + "." + digits[-fraction:]
        sign = "-" if rng.getrandbits(1) else ""
        text = f"{sign}{digits}e{rng.randrange(-400, 401)}"
        if math.isfinite(float(text)):
            texts.append(text)
        else:
            with pytest.raises(jsonmodem.JSONDecodeError, match="infinity"):
                jsonmodem.loads(text)
    actual = jsonmodem.loads("[" + ",".join(texts) + "]")
    expected = [float(text) for text in texts]
    assert [struct.pack("<d", value) for value in actual] == [struct.pack("<d", value) for value in expected]


@pytest.mark.parametrize("suffix", ["-0", "+0", "_0", "true", "null", "[", "{", '"', "\u00e9"])
def test_float_token_requires_a_delimiter(suffix):
    for text in ("1.25e2", "-0.5e-1"):
        with pytest.raises(jsonmodem.JSONDecodeError):
            jsonmodem.loads(text + suffix)
        with pytest.raises(jsonmodem.JSONDecodeError):
            jsonmodem.loads("[" + text + suffix + "]")
