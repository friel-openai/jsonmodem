"""Date-prefix reuse must not retain time fields or state between calls."""

import json

import jsonmodem
import pytest

np = pytest.importorskip("numpy")

UNITS = ("Y", "M", "W", "D", "h", "m", "s", "ms", "us", "ns")
DATE_FLAGS = (0, 2, 8, 10, 128, 130, 136, 138)
STAMPS = (
    "1970-01-01T00:00:00.000000000",
    "1970-01-01T23:59:59.999999999",
    "1970-01-01T12:34:56.123456789",
    "1970-01-01T00:00:00.000001000",
    "1970-01-02T00:00:00.000000000",
    "1969-12-31T23:59:59.999999999",
    "1969-12-31T00:00:00.000000000",
    "2000-02-28T23:59:59.999999999",
    "2000-02-29T00:00:00.000000000",
    "2000-02-29T09:08:07.654321000",
    "2000-03-01T00:00:00.000000000",
    "2000-02-29T10:00:00.000000000",
)


def expected(value, flags):
    # NumPy supplies an independent calendar formatter, including negative months
    # that are deliberately not passed to orjson's native formatter.
    if isinstance(value, np.ndarray):
        return [expected(item, flags) for item in value]
    whole, fraction = str(np.datetime_as_string(value, unit="us")).split(".")
    text = whole if flags & 8 or fraction == "000000" else f"{whole}.{fraction}"
    if flags & 2:
        text += "Z" if flags & 128 else "+00:00"
    return text


@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize("flags", DATE_FLAGS)
@pytest.mark.parametrize("shape", ((12,), (3, 4), (2, 2, 3)))
@pytest.mark.parametrize("format_flags", (0, 1 | 1024))
def test_day_transitions_keep_clock_and_options(unit, flags, shape, format_flags):
    array = np.array(STAMPS, dtype=f"datetime64[{unit}]").reshape(shape)
    value = {"dates": array, "scalar": array.flat[0]}
    output = jsonmodem.dumps(value, option=16 | flags | format_flags)
    assert json.loads(output) == {
        "dates": expected(array, flags),
        "scalar": expected(array.flat[0], flags),
    }


@pytest.mark.parametrize("flags", DATE_FLAGS)
def test_nanosecond_minimum_retains_existing_date(flags):
    array = np.array([0, -(1 << 63), -(1 << 63) + 1, 0], dtype="datetime64[ns]")
    minimum = "1677-09-21T00:12:43"
    if not flags & 8:
        minimum += ".145224"
    suffix = ("Z" if flags & 128 else "+00:00") if flags & 2 else ""
    epoch = "1970-01-01T00:00:00" + suffix
    output = jsonmodem.dumps(array, option=16 | flags)
    assert json.loads(output) == [epoch, minimum + suffix, minimum + suffix, epoch]


@pytest.mark.parametrize("flags", DATE_FLAGS)
def test_extreme_valid_years_and_repeated_days(flags):
    array = np.array((
        "0000-01-01T00:00:00.000000",
        "0000-01-01T23:59:59.999999",
        "0000-02-29T12:34:56.123456",
        "9999-12-31T00:00:00.000001",
        "9999-12-31T23:59:59.999999",
        "0000-01-01T00:00:00.000000",
    ), dtype="datetime64[us]")
    assert json.loads(jsonmodem.dumps(array, option=16 | flags)) == expected(array, flags)


@pytest.mark.parametrize("unit", UNITS[:-1])
@pytest.mark.parametrize("invalid", (-(1 << 63), (1 << 63) - 1))
def test_overflow_after_valid_values_still_raises(unit, invalid):
    array = np.array([0, 0, invalid, 0], dtype=f"datetime64[{unit}]")
    with pytest.raises(TypeError, match="unrepresentable numpy.datetime64"):
        jsonmodem.dumps(array, option=16)


@pytest.mark.parametrize("invalid", ("-0001-12-31", "10000-01-01"))
def test_invalid_year_after_valid_day_still_raises(invalid):
    array = np.array(["2000-01-01", "2000-01-01", invalid], dtype="datetime64[us]")
    with pytest.raises(TypeError, match="unrepresentable numpy.datetime64"):
        jsonmodem.dumps(array, option=16)


@pytest.mark.parametrize("unit, label", (
    ("ps", "picoseconds"), ("fs", "femtoseconds"),
    ("as", "attoseconds"), ("", "generic"),
))
def test_empty_snapshot_still_skips_unit_errors(unit, label):
    native = jsonmodem._native._numpy_dumps
    assert native(b"", (0,), "M", 8, unit, 16, 0) == b"[]"
    with pytest.raises(TypeError, match=f"unsupported numpy.datetime64 unit: {label}"):
        native(bytes(8), (1,), "M", 8, unit, 16, 0)


@pytest.mark.parametrize("unit", ("2us", "17ns", "3M"))
def test_unit_multipliers_remain_rejected(unit):
    array = np.array([0, 0, 1], dtype=f"datetime64[{unit}]")
    for value in (array, array[0]):
        with pytest.raises(TypeError, match="unit multipliers are not supported"):
            jsonmodem.dumps(value, option=16)


def test_each_call_uses_its_own_values_units_and_options():
    for unit, flags in (("us", 2), ("ns", 130), ("s", 8), ("us", 0)):
        array = np.array(STAMPS, dtype=f"datetime64[{unit}]")
        for index in (0, 4, 7, 8):
            values = array[index:index + 4].copy()
            assert json.loads(jsonmodem.dumps(values, option=16 | flags)) == expected(values, flags)
            values[:] = array[-1]
            assert json.loads(jsonmodem.dumps(values, option=16 | flags)) == expected(values, flags)
