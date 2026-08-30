"""Date/time formatting, fallback callbacks, and ownership during serialization."""

import dataclasses
import datetime
import gc
import json
import sys

import pytest

import jsonmodem
from test_streaming_security import run_python


OPTIONS = (0, 2, 8, 10, 128, 130, 136, 138)
FRACTIONS = (0, 1, 9, 10, 99, 100, 999, 1000, 9999, 10000, 40974, 99999, 100000, 999999)


def expected_text(value, option):
    if type(value) is datetime.date:
        return value.isoformat()
    text = value.isoformat(timespec="seconds" if option & 8 else "auto")
    if type(value) is datetime.datetime:
        if value.tzinfo is None and option & 2:
            text += "+00:00"
        if option & 128 and text.endswith("+00:00"):
            text = text[:-6] + "Z"
    return text


@pytest.mark.parametrize("option", OPTIONS)
@pytest.mark.parametrize("year,month,day", [
    (1, 1, 1), (9, 2, 3), (99, 10, 9), (999, 11, 30),
    (1000, 12, 31), (2000, 2, 29), (9999, 12, 31),
])
@pytest.mark.parametrize("kind", ["date", "naive", "utc"])
def test_date_components(year, month, day, kind, option):
    if kind == "date":
        value = datetime.date(year, month, day)
    else:
        value = datetime.datetime(year, month, day, 23, 59, 59, 123456,
                                  tzinfo=datetime.timezone.utc if kind == "utc" else None)
    expected = json.dumps(expected_text(value, option)).encode()
    assert jsonmodem.dumps(value, option=option) == expected
    oracle = pytest.importorskip("orjson")
    assert oracle.dumps(value, option=option) == expected


@pytest.mark.parametrize("option", OPTIONS)
@pytest.mark.parametrize("microsecond", FRACTIONS)
@pytest.mark.parametrize("kind", ["time", "naive", "utc"])
def test_time_components_and_fraction_padding(microsecond, kind, option):
    if kind == "time":
        value = datetime.time(0, 4, 5, microsecond, fold=1)
    else:
        value = datetime.datetime(2024, 2, 29, 0, 4, 5, microsecond, fold=1,
                                  tzinfo=datetime.timezone.utc if kind == "utc" else None)
    expected = json.dumps(expected_text(value, option)).encode()
    assert jsonmodem.dumps(value, option=option) == expected


@pytest.mark.parametrize("option", [0, 1, 32, 1024, 1 | 32 | 1024, 2 | 8 | 128])
def test_dates_in_containers_and_dataclasses(option):
    @dataclasses.dataclass
    class Record:
        value: object

    values = [datetime.date(1, 2, 3), datetime.time(4, 5, 6, 40974),
              datetime.datetime(9999, 12, 31, 23, 59, 59, 999999, datetime.timezone.utc)]
    value = {"z": tuple(values), "a": Record(values)}
    text = [expected_text(item, option) for item in values]
    expected = json.dumps({"z": text, "a": {"value": text}},
                          indent=2 if option & 1 else None,
                          separators=(",", ": ") if option & 1 else (",", ":"),
                          sort_keys=bool(option & 32)).encode()
    if option & 1024:
        expected += b"\n"
    assert jsonmodem.dumps(value, option=option) == expected


@pytest.mark.parametrize("option", OPTIONS)
@pytest.mark.parametrize("seconds", [0, 19800, -12600, 19845, -31])
def test_other_fixed_timezones_keep_minute_rounding(seconds, option):
    tz = datetime.timezone(datetime.timedelta(seconds=seconds), "named offset")
    value = datetime.datetime(2024, 1, 2, 3, 4, 5, 123456, tz)
    assert tz is not datetime.timezone.utc
    minutes = (abs(seconds) + 30) // 60
    offset = "Z" if not minutes and option & 128 else (
        f"{'-' if seconds < 0 else '+'}{minutes // 60:02}:{minutes % 60:02}"
    )
    fraction = "" if option & 8 else ".123456"
    assert jsonmodem.dumps(value, option=option) == (
        f'"2024-01-02T03:04:05{fraction}{offset}"'.encode()
    )


@pytest.mark.parametrize("option", OPTIONS)
def test_aware_time_keeps_its_error(option):
    value = datetime.time(1, 2, 3, tzinfo=datetime.timezone.utc)
    with pytest.raises(TypeError, match="timezone library is not supported"):
        jsonmodem.dumps(value, option=option)


@pytest.mark.parametrize("kind", [datetime.date, datetime.time, datetime.datetime])
@pytest.mark.parametrize("option", [0, 256, 512, 256 | 512 | 128])
def test_subclasses_are_passed_to_default(kind, option):
    class Subclass(kind):
        def __getattribute__(self, name):
            if name in ("year", "month", "day", "hour", "minute", "second", "microsecond", "tzinfo"):
                raise AssertionError("subclass fields must not be read")
            return super().__getattribute__(name)

    value = Subclass(1, 2, 3)
    calls = []

    def default(item):
        calls.append(item)
        return "subclass"

    assert jsonmodem.dumps(value, default=default, option=option) == b'"subclass"'
    assert len(calls) == 1 and calls[0] is value
    with pytest.raises(TypeError, match="not JSON serializable"):
        jsonmodem.dumps(value, option=option)


@pytest.mark.parametrize("value", [datetime.date(2024, 1, 2), datetime.time(3, 4, 5),
                                  datetime.datetime(2024, 1, 2, 3, 4, 5)])
@pytest.mark.parametrize("option", OPTIONS)
def test_passthrough_preserves_callback_selection(value, option):
    calls = []

    def default(item):
        calls.append(item)
        return ["custom"]

    assert jsonmodem.dumps(value, default=default, option=option | 512) == b'["custom"]'
    assert len(calls) == 1 and calls[0] is value


def test_default_mutation_keeps_captured_dates_alive():
    marker = object()
    parent = [marker, datetime.date(2024, 1, 2), datetime.time(3, 4, 5, 40974)]

    def default(value):
        assert value is marker
        parent.clear()
        gc.collect()
        return datetime.datetime(1, 2, 3, 4, 5, 6, tzinfo=datetime.timezone.utc)

    assert jsonmodem.dumps(parent, default=default) == (
        b'["0001-02-03T04:05:06+00:00","2024-01-02","03:04:05.040974"]'
    )
    assert parent == []


def test_timezone_callback_can_mutate_and_reenter():
    calls = []
    parent = []

    class Timezone(datetime.tzinfo):
        def __eq__(self, other):
            raise AssertionError("UTC must be checked by identity")

        def utcoffset(self, value):
            calls.append("offset")
            parent.clear()
            gc.collect()
            assert jsonmodem.dumps(datetime.date(7, 2, 3)) == b'"0007-02-03"'
            return datetime.timedelta(0)

    parent.extend([datetime.datetime(2024, 1, 2, tzinfo=Timezone()), datetime.date(9999, 12, 31)])
    assert jsonmodem.dumps(parent, option=128) == b'["2024-01-02T00:00:00Z","9999-12-31"]'
    assert calls == ["offset"] and parent == []


def test_timezone_callback_exception_is_not_swallowed():
    error = RuntimeError("timezone callback")

    class Timezone(datetime.tzinfo):
        def utcoffset(self, value):
            raise error

    value = datetime.datetime(2024, 1, 2, tzinfo=Timezone())
    with pytest.raises(RuntimeError) as caught:
        jsonmodem.dumps(value)
    assert caught.value is error


def test_datetime_dictionary_keys_keep_existing_conversion():
    value = {datetime.date(7, 2, 3): datetime.time(4, 5, 6, 40974),
             datetime.datetime(2024, 1, 2): datetime.date(9999, 12, 31)}
    assert jsonmodem.dumps(value, option=4 | 2 | 128) == (
        b'{"0007-02-03":"04:05:06.040974","2024-01-02T00:00:00Z":"9999-12-31"}'
    )


@pytest.mark.parametrize("depth", [1, 2, 253, 254])
def test_datetime_nesting_preserves_limits(depth):
    value = datetime.datetime(2024, 1, 2)
    for _ in range(depth):
        value = [value]
    assert jsonmodem.dumps(value) == b"[" * depth + b'"2024-01-02T00:00:00"' + b"]" * depth
    if depth == 254:
        with pytest.raises(TypeError, match="Recursion limit"):
            jsonmodem.dumps([value])


@pytest.mark.skipif(sys.implementation.name != "cpython", reason="CPython pickle-state fields")
@pytest.mark.parametrize("state_type", [bytes, str])
@pytest.mark.parametrize("kind,state,expected", [
    (datetime.date, b"\x00\x00\x01\x01", "0000-01-01"),
    (datetime.date, b"\xff\xff\x01\x01", "65535-01-01"),
    (datetime.date, b"\x07\xe8\x02\x00", "2024-02-00"),
    (datetime.date, b"\x07\xe8\x02\xff", "2024-02-255"),
    (datetime.datetime, b"\xff\xff\x01\x01\x00\x00\x00\x00\x00\x00", "65535-01-01T00:00:00"),
    (datetime.datetime, b"\x07\xe8\x01\xff\xff\xff\xff\xff\xff\xff", "2024-01-255T255:255:255.16777215"),
    (datetime.time, b"\x17\xff\xff\xff\xff\xff", "23:255:255.16777215"),
])
def test_pickle_state_out_of_range_fields_keep_fallback(kind, state, expected, state_type):
    # These are accepted CPython constructor states, not malformed native pointers.
    value = kind(state if state_type is bytes else state.decode("latin1"))
    assert type(value) is kind
    assert jsonmodem.dumps(value) == json.dumps(expected).encode()
    assert jsonmodem.dumps([value]) == b"[" + json.dumps(expected).encode() + b"]"


@pytest.mark.skipif(
    sys.implementation.name != "cpython" or not getattr(sys, "_is_gil_enabled", lambda: True)(),
    reason="checks GIL-enabled CPython reference counts",
)
def test_datetime_owners_are_released_after_each_call():
    values = [datetime.date(2024, 1, 2), datetime.time(3, 4, 5, 123456),
              datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)]
    jsonmodem.dumps(values)
    before = [sys.getrefcount(item) for item in values]
    for _ in range(100):
        jsonmodem.dumps(values)
    gc.collect()
    assert [sys.getrefcount(item) for item in values] == before


@pytest.mark.skipif(sys.implementation.name != "cpython", reason="CPython datetime C API")
def test_missing_datetime_c_api_uses_python_fallback_then_recovers():
    result = run_python('''
import datetime
import sys
api = datetime.datetime_CAPI
del datetime.datetime_CAPI
try:
    import jsonmodem
    values = [datetime.date(2024, 1, 2), datetime.time(3, 4, 5, 40974),
              datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)]
    expected = b'["2024-01-02","03:04:05.040974","2024-01-02T00:00:00+00:00"]'
    assert "orjson" not in sys.modules
    assert jsonmodem.dumps(values) == expected
finally:
    datetime.datetime_CAPI = api
assert jsonmodem.dumps(values) == expected
assert "orjson" not in sys.modules
''')
    assert result.returncode == 0, result.stdout + result.stderr
