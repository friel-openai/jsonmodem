"""NumPy date digits retain padding, calendar bounds and output options."""

from datetime import datetime
import json
import sys

import jsonmodem
from jsonmodem import _jsonmodem as native
import pytest


DATE_FLAGS = (0, 2, 8, 10, 128, 130, 136, 138)
FORMAT_FLAGS = (0, 1, 1024, 1025)
EPOCH = datetime(1970, 1, 1)


def native_dates(values, unit, flags, shape):
    """Exercise immutable i64 snapshots without NumPy date conversions."""
    raw = b"".join(value.to_bytes(8, sys.byteorder, signed=True) for value in values)
    return native._numpy_dumps(
        raw, shape, "M", 8, unit, jsonmodem.OPT_SERIALIZE_NUMPY | flags, 0
    )


def utc_suffix(flags):
    if not flags & jsonmodem.OPT_NAIVE_UTC:
        return ""
    return "Z" if flags & jsonmodem.OPT_UTC_Z else "+00:00"


def expected_json(value, flags):
    if flags & jsonmodem.OPT_INDENT_2:
        output = json.dumps(value, indent=2).encode("ascii")
    else:
        output = json.dumps(value, separators=(",", ":")).encode("ascii")
    return output + b"\n" if flags & jsonmodem.OPT_APPEND_NEWLINE else output


def epoch_micros(value):
    """Avoid floating-point timestamps and the process's local time zone."""
    delta = value - EPOCH
    return (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds


@pytest.mark.parametrize("scale,fixed", ((100, 47), (1, 5300)), ids=("century", "year"))
@pytest.mark.parametrize("flags", DATE_FLAGS)
def test_each_year_pair_in_native_snapshots(scale, fixed, flags):
    years = [number * scale + fixed for number in range(100)]
    expected = [f"{year:04d}-01-01T00:00:00{utc_suffix(flags)}" for year in years]
    output = native_dates([year - 1970 for year in years], "Y", flags, (100,))
    assert output == expected_json(expected, flags)


@pytest.mark.parametrize(
    "scale,fixed", ((10_000, 1234), (100, 120034), (1, 123400)),
    ids=("first_pair", "middle_pair", "last_pair"),
)
@pytest.mark.parametrize("flags", DATE_FLAGS)
def test_fractional_pairs_vary_independently(scale, fixed, flags):
    # Other pairs stay nonzero, so pair 00 must be emitted inside a fraction.
    fractions = [number * scale + fixed for number in range(100)]
    values = [946_684_800_000_000 + fraction for fraction in fractions]
    expected = []
    for fraction in fractions:
        text = "2000-01-01T00:00:00"
        if not flags & jsonmodem.OPT_OMIT_MICROSECONDS:
            text += f".{fraction:06d}"
        expected.append(text + utc_suffix(flags))
    assert native_dates(values, "us", flags, (100,)) == expected_json(expected, flags)


@pytest.mark.parametrize("field,numbers", (
    ("month", range(1, 13)),
    ("day", range(1, 32)),
    ("hour", range(24)),
    ("minute", range(60)),
    ("second", range(60)),
))
@pytest.mark.parametrize("flags", DATE_FLAGS)
def test_valid_calendar_fields_in_native_snapshots(field, numbers, flags):
    dates = [datetime(2000, 1, 1).replace(**{field: number}) for number in numbers]
    values = [epoch_micros(date) // 1_000_000 for date in dates]
    expected = [date.isoformat(timespec="seconds") + utc_suffix(flags) for date in dates]
    assert native_dates(values, "s", flags, (len(values),)) == expected_json(expected, flags)


@pytest.mark.parametrize("flags", DATE_FLAGS)
@pytest.mark.parametrize("format_flags", FORMAT_FLAGS)
def test_public_date_boundaries_and_output_options(flags, format_flags):
    np = pytest.importorskip("numpy")
    dates = (
        datetime(1, 1, 1),
        datetime(99, 12, 31, 23, 59, 59, 999999),
        datetime(100, 1, 1),
        datetime(1900, 2, 28, 23, 59, 59, 999999),
        datetime(1900, 3, 1),
        datetime(1969, 12, 31, 23, 59, 59, 999999),
        datetime(1970, 1, 1),
        datetime(1999, 12, 31, 23, 59, 59, 999999),
        datetime(2000, 1, 1),
        datetime(2000, 2, 29, 23, 59, 59, 999999),
        datetime(2000, 3, 1),
        datetime(2099, 12, 31, 23, 59, 59, 999999),
        datetime(2100, 1, 1),
        datetime(2100, 2, 28, 23, 59, 59, 999999),
        datetime(2100, 3, 1),
        datetime(9999, 12, 31, 23, 59, 59, 999999),
    )
    array = np.array([epoch_micros(date) for date in dates], dtype=np.int64).view("datetime64[us]")
    texts = []
    for date in dates:
        fractional = date.microsecond and not flags & jsonmodem.OPT_OMIT_MICROSECONDS
        text = date.isoformat(timespec="microseconds" if fractional else "seconds")
        texts.append(text + utc_suffix(flags))
    option = jsonmodem.OPT_SERIALIZE_NUMPY | flags | format_flags
    for scalar, text in zip(array, texts):
        assert jsonmodem.dumps(scalar, option=option) == expected_json(text, format_flags)
    rows = [texts[index:index + 4] for index in range(0, 16, 4)]
    for value, expected in (
        (array, texts),
        (array.reshape(4, 4), rows),
        ({"dates": [array.reshape(2, 2, 4)], "last": array[-1]},
         {"dates": [[rows[:2], rows[2:]]], "last": texts[-1]}),
    ):
        assert jsonmodem.dumps(value, option=option) == expected_json(expected, format_flags)


@pytest.mark.parametrize("unit,value", (
    ("Y", -1971),
    ("Y", 8030),
    ("M", -23641),
    ("M", 96360),
    ("Y", (1 << 63) - 1),
    ("M", -(1 << 63)),
))
@pytest.mark.parametrize("placement", ("scalar", "first", "last"))
def test_invalid_calendar_is_rejected_before_digit_formatting(unit, value, placement):
    if placement == "scalar":
        values, shape = [value], ()
    else:
        values = [value, 0] if placement == "first" else [0, value]
        shape = (2,)
    flags = jsonmodem.OPT_NAIVE_UTC | jsonmodem.OPT_OMIT_MICROSECONDS | jsonmodem.OPT_UTC_Z
    with pytest.raises(TypeError, match="unrepresentable numpy.datetime64"):
        native_dates(values, unit, flags, shape)
