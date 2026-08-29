"""Fixed-width NumPy timestamps retain calendar and option behavior."""

import json

import jsonmodem
import pytest

np = pytest.importorskip("numpy")

UNITS = ("Y", "M", "W", "D", "h", "m", "s", "ms", "us", "ns")
DATE_FLAGS = (0, 2, 8, 10, 128, 130, 136, 138)
# orjson 3.11.9 can terminate the process on negative month offsets. Pre-epoch
# timestamps therefore have independent expected results below.
DATES = (
    "1970-01-01T00:00:00.000000000",
    "1970-12-31T23:59:59.999999999",
    "1970-01-01T00:00:00.000000001",
    "1970-01-01T00:00:00.000001000",
    "2000-02-29T01:02:03.000010001",
    "2001-03-04T05:06:07.000099999",
    "2002-04-05T06:07:08.000100000",
    "2003-05-06T07:08:09.000999000",
    "2004-06-07T08:09:10.001000123",
    "2005-07-08T09:10:11.009999999",
    "2006-08-09T10:11:12.010000000",
    "2007-09-10T11:12:13.099999999",
    "2008-10-11T12:13:14.100000000",
    "2009-11-12T13:14:15.999999999",
    "2010-12-31T23:59:59.123456789",
    "2099-12-31T23:59:59.999999999",
)


@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize("flags", DATE_FLAGS)
@pytest.mark.parametrize("container", ("scalar", "array", "matrix", "nested", "empty"))
def test_dates_match_orjson(unit, flags, container):
    orjson = pytest.importorskip("orjson")
    array = np.array(DATES, dtype="datetime64[ns]").astype(f"datetime64[{unit}]")
    values = {
        "scalar": array,
        "array": (array,),
        "matrix": (array.reshape(4, 4),),
        "nested": ({"dates": [array.reshape(2, 2, 4)]},),
        "empty": (array[:0],),
    }[container]
    option = jsonmodem.OPT_SERIALIZE_NUMPY | flags
    for value in values:
        assert jsonmodem.dumps(value, option=option) == orjson.dumps(value, option=option)


@pytest.mark.parametrize("unit", ("Y", "s", "us", "ns"))
@pytest.mark.parametrize("flags", DATE_FLAGS)
@pytest.mark.parametrize("format_flags", (1, 1024, 1 | 1024))
def test_dates_with_indent_and_newline(unit, flags, format_flags):
    orjson = pytest.importorskip("orjson")
    array = np.array(DATES, dtype="datetime64[ns]").astype(f"datetime64[{unit}]")
    value = {"first": array[0], "dates": array.reshape(2, 2, 4), "empty": array[:0]}
    option = jsonmodem.OPT_SERIALIZE_NUMPY | flags | format_flags
    assert jsonmodem.dumps(value, option=option) == orjson.dumps(value, option=option)


def utc_suffix(flags):
    if not flags & jsonmodem.OPT_NAIVE_UTC:
        return ""
    return "Z" if flags & jsonmodem.OPT_UTC_Z else "+00:00"


@pytest.mark.parametrize("unit, expected", (
    ("Y", "1969-01-01T00:00:00"),
    ("M", "1969-12-01T00:00:00"),
    ("W", "1969-12-25T00:00:00"),
    ("D", "1969-12-31T00:00:00"),
    ("h", "1969-12-31T23:00:00"),
    ("m", "1969-12-31T23:59:00"),
    ("s", "1969-12-31T23:59:59"),
    ("ms", "1969-12-31T23:59:59.999000"),
    ("us", "1969-12-31T23:59:59.999999"),
    ("ns", "1969-12-31T23:59:59.999999"),
))
@pytest.mark.parametrize("flags", DATE_FLAGS)
def test_pre_epoch_values_without_native_oracle(unit, expected, flags):
    if flags & jsonmodem.OPT_OMIT_MICROSECONDS:
        expected = expected.split(".", 1)[0]
    expected += utc_suffix(flags)
    scalar = np.datetime64(-1, unit)
    array = np.array([-1], dtype=f"datetime64[{unit}]")
    for value, decoded in (
        (scalar, expected),
        (array, [expected]),
        (array.reshape(1, 1), [[expected]]),
        ({"date": scalar}, {"date": expected}),
    ):
        output = jsonmodem.dumps(value, option=jsonmodem.OPT_SERIALIZE_NUMPY | flags)
        assert json.loads(output) == decoded


@pytest.mark.parametrize("months, expected", (
    (-1, "1969-12-01T00:00:00"),
    (-12, "1969-01-01T00:00:00"),
    (-13, "1968-12-01T00:00:00"),
    (-841, "1899-12-01T00:00:00"),
))
def test_negative_month_remainders(months, expected):
    output = jsonmodem.dumps(np.datetime64(months, "M"), option=jsonmodem.OPT_SERIALIZE_NUMPY)
    assert json.loads(output) == expected


@pytest.mark.parametrize("flags", DATE_FLAGS)
def test_every_supported_year_has_four_digits(flags):
    # Check the hardened calendar range without calling the native oracle on
    # years outside the ordinary dates used by the oracle tests above.
    years = np.arange(10_000, dtype=np.int64)
    values = (years - 1970).view("datetime64[Y]")
    output = jsonmodem.dumps(values, option=jsonmodem.OPT_SERIALIZE_NUMPY | flags)
    expected = [f"{year:04d}-01-01T00:00:00{utc_suffix(flags)}" for year in range(10_000)]
    assert json.loads(output) == expected


@pytest.mark.parametrize("flags", DATE_FLAGS)
def test_each_fractional_digit_pair(flags):
    fractions = [number * 10_101 for number in range(100)]
    values = np.array([946_684_800_000_000 + fraction for fraction in fractions], dtype=np.int64)
    values = values.view("datetime64[us]")
    output = jsonmodem.dumps(values, option=jsonmodem.OPT_SERIALIZE_NUMPY | flags)
    expected = []
    for fraction in fractions:
        text = "2000-01-01T00:00:00"
        if fraction and not flags & jsonmodem.OPT_OMIT_MICROSECONDS:
            text += f".{fraction:06d}"
        expected.append(text + utc_suffix(flags))
    assert json.loads(output) == expected


@pytest.mark.parametrize("value, expected", (
    (-1_000_001, "1969-12-31T23:59:59.998999"),
    (-1_000_000, "1969-12-31T23:59:59.999000"),
    (-1_001, "1969-12-31T23:59:59.999998"),
    (-1_000, "1969-12-31T23:59:59.999999"),
    (-999, "1969-12-31T23:59:59.999999"),
    (-1, "1969-12-31T23:59:59.999999"),
    (0, "1970-01-01T00:00:00"),
    (1, "1970-01-01T00:00:00"),
    (999, "1970-01-01T00:00:00"),
    (1_000, "1970-01-01T00:00:00.000001"),
    (1_001, "1970-01-01T00:00:00.000001"),
    (999_999_999, "1970-01-01T00:00:00.999999"),
))
@pytest.mark.parametrize("flags", DATE_FLAGS)
def test_nanoseconds_round_toward_negative_infinity(value, expected, flags):
    if flags & jsonmodem.OPT_OMIT_MICROSECONDS:
        expected = expected.split(".", 1)[0]
    output = jsonmodem.dumps(np.datetime64(value, "ns"), option=16 | flags)
    assert json.loads(output) == expected + utc_suffix(flags)


@pytest.mark.parametrize("unit", UNITS[:-1])
@pytest.mark.parametrize("value", (-(1 << 63), (1 << 63) - 1))
def test_extreme_calendar_values_still_raise(unit, value):
    # These inputs are deliberately not passed to orjson: the checked
    # arithmetic is also intended to reject values that can fault a formatter.
    for obj in (np.datetime64(value, unit), np.array([value], dtype=f"datetime64[{unit}]")):
        with pytest.raises(TypeError, match="unrepresentable numpy.datetime64"):
            jsonmodem.dumps(obj, option=jsonmodem.OPT_SERIALIZE_NUMPY)


@pytest.mark.parametrize("year", (-1, 10_000))
@pytest.mark.parametrize("unit", ("Y", "M"))
def test_calendar_range_is_unchanged(year, unit):
    value = year - 1970
    if unit == "M":
        value *= 12
    with pytest.raises(TypeError, match="unrepresentable numpy.datetime64"):
        jsonmodem.dumps(np.datetime64(value, unit), option=jsonmodem.OPT_SERIALIZE_NUMPY)
