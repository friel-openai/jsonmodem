"""Exact-output checks for staging boundaries and direct integer formatting."""

import random

import jsonmodem
import orjson
import pytest


@pytest.mark.parametrize("length", [0, 1, 19, 20, 21, 255, 256, 511, 512, 513, 1023, 1024, 1025])
@pytest.mark.parametrize("option", [0, 1, 32, 1024, 1 | 32 | 1024])
def test_output_boundaries(length, option):
    value = [{"shared": "x" * length, "integer": -(2**63), "escaped": "\n" * length},
             [2**64 - 1, 0, 10, -100], {"shared": "tail", "integer": 1234}]
    assert jsonmodem.dumps(value, option=option) == orjson.dumps(value, option=option)


def test_all_decimal_boundaries():
    values = {-(2**63), 2**63 - 1, 2**63, 2**64 - 1, 0}
    for exponent in range(20):
        for delta in (-1, 0, 1):
            for sign in (-1, 1):
                value = sign * (10**exponent + delta)
                if -(2**63) <= value < 2**64:
                    values.add(value)
    values = sorted(values)
    assert jsonmodem.dumps(values) == orjson.dumps(values)
    assert jsonmodem.dumps({n: n for n in values}, option=4) == orjson.dumps({n: n for n in values}, option=4)


def test_random_integers():
    rng = random.Random(123)
    values = [rng.randrange(-(2**63), 2**64) for _ in range(100000)]
    assert jsonmodem.dumps(values) == orjson.dumps(values)


@pytest.mark.parametrize("value", [-(2**63) - 1, 2**64, -(2**53), 2**53])
def test_range_errors(value):
    option = 64 if abs(value) == 2**53 else 0
    with pytest.raises(TypeError):
        jsonmodem.dumps([0, value], option=option)
