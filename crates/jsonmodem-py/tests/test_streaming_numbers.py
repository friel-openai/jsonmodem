"""Numeric materialization preserves exact values at every chunk boundary."""

import json
import math
import random
import struct
import sys

import pytest

import jsonmodem


NUMBERS = [
    "0", "-0", "-1", "9007199254740993", "-9223372036854775808",
    "9223372036854775807", "9223372036854775808", "18446744073709551615",
    "-9223372036854775809", "18446744073709551616", str(2**200),
    "0.0", "-0.0", "-0e400", "1e2", "-123.456e-7", "5e-324",
    "2.2250738585072011e-308", "1.7976931348623157e308",
]


def same_number(actual, expected):
    assert type(actual) is type(expected)
    if isinstance(expected, float):
        assert struct.pack("<d", actual) == struct.pack("<d", expected)
    else:
        assert actual == expected


@pytest.mark.parametrize("text", NUMBERS)
@pytest.mark.parametrize("byte_views", [False, True])
def test_every_numeric_byte_split(text, byte_views):
    document = text.encode()
    expected = json.loads(text)
    for split in range(len(document) + 1):
        chunks = [document[:split], document[split:]]
        parser = jsonmodem.JsonModem(byte_views=byte_views)
        events = list(parser.feed(chunks)) + list(parser.finish())
        numbers = [value for kind, _, value in events if kind == "number"]
        assert len(numbers) == 1
        same_number(numbers[0], expected)

        values = jsonmodem.JsonModemValues()
        list(values.feed(chunks))
        list(values.finish())
        same_number(values.view().snapshot(), expected)


def test_partial_numbers_wait_for_completion():
    parser = jsonmodem.JsonModemValues()
    expected = [[], [], [1], [1], [1], [1], [1, 2.5], [1, 2.5],
                [1, 2.5], [1, 2.5], [1, 2.5], [1, 2.5, -300.0]]
    for byte, value in zip(b"[1,2.5,-3e2]", expected):
        list(parser.feed(bytes([byte])))
        snapshot = parser.view().snapshot()
        assert len(snapshot) == len(value)
        for actual, wanted in zip(snapshot, value):
            same_number(actual, wanted)
    list(parser.finish())


@pytest.mark.parametrize("chunk_size", [1, 7, 64, 512, 4096])
def test_seeded_numeric_stream(chunk_size):
    rng = random.Random(7727)
    numbers = [rng.randrange(-(2**63), 2**64) for _ in range(1000)]
    numbers.extend(rng.randrange(-(2**200), 2**200) for _ in range(30))
    floats = [struct.unpack("<d", rng.getrandbits(64).to_bytes(8, "little"))[0] for _ in range(1000)]
    numbers.extend(value for value in floats if math.isfinite(value))
    rng.shuffle(numbers)
    document = json.dumps(numbers, separators=(",", ":")).encode()
    chunks = [document[index:index + chunk_size] for index in range(0, len(document), chunk_size)]
    parser = jsonmodem.JsonModem()
    events = list(parser.feed(chunks)) + list(parser.finish())
    actual = [value for kind, _, value in events if kind == "number"]
    assert len(actual) == len(numbers)
    for value, expected in zip(actual, numbers):
        same_number(value, expected)

    parser = jsonmodem.JsonModemValues()
    list(parser.feed(chunks))
    list(parser.finish())
    actual = parser.view().snapshot()
    assert len(actual) == len(numbers)
    for value, expected in zip(actual, numbers):
        same_number(value, expected)


@pytest.mark.parametrize("text", ["1e400", "-1e400", "1.7976931348623159e308", "1e9999999999999999999"])
def test_nonfinite_streaming_numbers_are_rejected(text):
    for parser_type in (jsonmodem.JsonModem, jsonmodem.JsonModemValues):
        parser = parser_type()
        with pytest.raises(jsonmodem.JsonModemSyntaxError):
            list(parser.feed(text.encode()))
            list(parser.finish())


@pytest.mark.skipif(not hasattr(sys, "set_int_max_str_digits"), reason="Python has no integer digit limit")
@pytest.mark.parametrize("byte_views", [False, True])
def test_large_streaming_integers_keep_python_digit_limits(byte_views):
    previous = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(640)
        document = b"9" * 641
        parser = jsonmodem.JsonModem(byte_views=byte_views)
        with pytest.raises(ValueError, match="limit"):
            for event in parser.feed(document + b" "):
                tuple(event)
        values = jsonmodem.JsonModemValues()
        list(values.feed(document))
        list(values.finish())
        with pytest.raises(ValueError, match="limit"):
            values.view().snapshot()

        sys.set_int_max_str_digits(0)
        expected = int(document)
        parser = jsonmodem.JsonModem(byte_views=byte_views)
        events = list(parser.feed(document)) + list(parser.finish())
        same_number(events[0][2], expected)
        same_number(values.view().snapshot(), expected)
    finally:
        sys.set_int_max_str_digits(previous)
